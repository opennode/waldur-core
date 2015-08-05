from __future__ import unicode_literals

import logging

from django.apps import apps
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.lru_cache import lru_cache

from nodeconductor.billing.backend import BillingBackendError
from nodeconductor.core.serializers import UnboundSerializerMethodField
from nodeconductor.structure.filters import filter_queryset_for_user


logger = logging.getLogger('nodeconductor.iaas')


def filter_clouds(clouds, request):
    related_clouds = clouds.all()

    try:
        user = request.user
        related_clouds = filter_queryset_for_user(related_clouds, user)
    except AttributeError:
        pass

    from nodeconductor.iaas.serializers import BasicCloudSerializer

    serializer_instance = BasicCloudSerializer(related_clouds, many=True, context={'request': request})

    return serializer_instance.data


def add_clouds_to_related_model(sender, fields, **kwargs):
    fields['clouds'] = UnboundSerializerMethodField(filter_clouds)


@lru_cache(maxsize=1)
def _get_default_security_groups():
    nc_settings = getattr(settings, 'NODECONDUCTOR', {})
    config_groups = nc_settings.get('DEFAULT_SECURITY_GROUPS', [])
    groups = []

    def get_icmp(config_rule, key):
        result = config_rule[key]

        if not isinstance(result, (int, long)):
            raise TypeError('wrong type for "%s": expected int, found %s' %
                            (key, type(result).__name__))

        if not -1 <= result <= 255:
            raise ValueError('wrong value for "%s": '
                             'expected value in range [-1, 255], found %d' %
                             key, result)

        return result

    def get_port(config_rule, key):
        result = config_rule[key]

        if not isinstance(result, (int, long)):
            raise TypeError('wrong type for "%s": expected int, found %s' %
                            (key, type(result).__name__))

        if not 1 <= result <= 65535:
            raise ValueError('wrong value for "%s": '
                             'expected value in range [1, 65535], found %d' %
                             (key, result))

        return result

    for config_group in config_groups:
        try:
            name = config_group['name']
            description = config_group['description']
            config_rules = config_group['rules']
            if not isinstance(config_rules, (tuple, list)):
                raise TypeError('wrong type for "rules": expected list, found %s' %
                                type(config_rules).__name__)

            rules = []
            for config_rule in config_rules:
                protocol = config_rule['protocol']
                if protocol == 'icmp':
                    from_port = get_icmp(config_rule, 'icmp_type')
                    to_port = get_icmp(config_rule, 'icmp_code')
                elif protocol in ('tcp', 'udp'):
                    from_port = get_port(config_rule, 'from_port')
                    to_port = get_port(config_rule, 'to_port')

                    if to_port < from_port:
                        raise ValueError('wrong value for "to_port": '
                                         'expected value less that from_port (%d), found %d' %
                                         (from_port, to_port))
                else:
                    raise ValueError('wrong value for "protocol": '
                                     'expected one of (tcp, udp, icmp), found %s' %
                                     protocol)

                rules.append({
                    'protocol': protocol,
                    'cidr': config_rule['cidr'],
                    'from_port': from_port,
                    'to_port': to_port,
                })
        except KeyError as e:
            logger.error('Skipping misconfigured security group: parameter "%s" not found',
                         e.message)
        except (ValueError, TypeError) as e:
            logger.error('Skipping misconfigured security group: %s',
                         e.message)
        else:
            groups.append({
                'name': name,
                'description': description,
                'rules': rules,
            })

    return groups


def create_initial_security_groups(sender, instance=None, created=False, **kwargs):
    if not created:
        return

    from nodeconductor.iaas.models import SecurityGroup

    for group in _get_default_security_groups():
        g = SecurityGroup.objects.create(
            name=group['name'],
            description=group['description'],
            cloud_project_membership=instance,
        )

        for rule in group['rules']:
            g.rules.create(**rule)


def prevent_deletion_of_instances_with_connected_backups(sender, instance, **kwargs):
    from nodeconductor.backup.models import Backup
    ct = ContentType.objects.get_for_model(instance._meta.model)
    connected_backups = Backup.objects.filter(content_type=ct, object_id=instance.id)

    if connected_backups.exists():
        raise models.ProtectedError(
            "Cannot delete instance because it has connected backups.",
            connected_backups
        )


def set_cpm_default_availability_zone(sender, instance=None, **kwargs):
    if not instance.availability_zone:
        OpenStackSettings = apps.get_model('iaas', 'OpenStackSettings')
        try:
            options = OpenStackSettings.objects.get(auth_url=instance.cloud.auth_url)
        except OpenStackSettings.DoesNotExist:
            pass
        else:
            instance.availability_zone = options.availability_zone


def check_instance_name_update(sender, instance=None, created=False, **kwargs):
    if created:
        return

    old_name = instance._old_values['name']
    if old_name != instance.name:
        from nodeconductor.iaas.tasks.zabbix import zabbix_update_host_visible_name
        zabbix_update_host_visible_name.delay(instance.uuid.hex)


# This signal has to be connected to all resources (NC-634)
def increase_quotas_usage_on_instance_creation(sender, instance=None, created=False, **kwargs):
    if created:
        instance.service_project_link.add_quota_usage('max_instances', 1)
        instance.service_project_link.add_quota_usage('ram', instance.ram)
        instance.service_project_link.add_quota_usage('vcpu', instance.cores)
        instance.service_project_link.add_quota_usage(
            'storage', instance.system_volume_size + instance.data_volume_size)


def decrease_quotas_usage_on_instances_deletion(sender, instance=None, **kwargs):
    instance.service_project_link.add_quota_usage('max_instances', -1)
    instance.service_project_link.add_quota_usage('vcpu', -instance.cores)
    instance.service_project_link.add_quota_usage('ram', -instance.ram)
    instance.service_project_link.add_quota_usage(
        'storage', -(instance.system_volume_size + instance.data_volume_size))


def track_order(sender, instance, name=None, source=None, **kwargs):
    order = instance.order
    try:
        if name == instance.begin_provisioning.__name__:
            order.add()

        if name == instance.set_online.__name__:
            if source == instance.States.PROVISIONING:
                order.accept()
            if source == instance.States.STARTING:
                order.update(flavor=instance.flavor_type)

        if name == instance.set_offline.__name__:
            if source == instance.States.STOPPING:
                order.update(flavor='offline')

        if name == instance.set_erred.__name__:
            if source == instance.States.PROVISIONING:
                order.cancel()

        if name == instance.set_resized.__name__:
            order.update(flavor='offline')

    except BillingBackendError:
        logger.exception("Failed to track order for resource %s" % instance)
        instance.state = instance.States.ERRED
        instance.save()


def delete_order(sender, instance=None, **kwargs):
    instance.order.delete()
