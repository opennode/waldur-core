from __future__ import unicode_literals

import logging

from django.apps import apps
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import models, router, DEFAULT_DB_ALIAS
from django.utils.lru_cache import lru_cache
import yaml

from nodeconductor.core import models as core_models
from nodeconductor.core.tasks import send_task
from nodeconductor.core.serializers import UnboundSerializerMethodField
from nodeconductor.quotas import handlers as quotas_handlers
from nodeconductor.structure.filters import filter_queryset_for_user


logger = logging.getLogger('nodeconductor.iaas')


def sync_openstack_settings(app_config, using=DEFAULT_DB_ALIAS, **kwargs):
    OpenStackSettings = app_config.get_model('OpenStackSettings')

    if not router.allow_migrate(using, OpenStackSettings):
        return

    nc_settings = getattr(settings, 'NODECONDUCTOR', {})
    openstacks = nc_settings.get('OPENSTACK_CREDENTIALS', ())

    if openstacks:
        import warnings
        logger.info("Sync OpenStack credentials")
        warnings.warn(
            "OPENSTACK_CREDENTIALS setting is deprecated. "
            "Create OpenStackSetting model instance instead.",
            DeprecationWarning,
        )

    for opts in openstacks:
        opts['availability_zone'] = opts.pop('default_availability_zone', '')
        queryset = OpenStackSettings._default_manager.using(using)
        if not queryset.filter(auth_url=opts['auth_url']).exists():
            queryset.create(**opts)


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


def sync_ssh_public_keys(task_name, public_key=None, project=None, user=None):
    """ Call supplied background task to push or remove SSH key(s).
        Use supplied public_key or lookup it by project & user.
    """
    CloudProjectMembership = apps.get_model('iaas', 'CloudProjectMembership')

    if public_key:
        ssh_public_key_uuids = [public_key.uuid.hex]
        membership_pks = filter_queryset_for_user(
            CloudProjectMembership.objects.all(), public_key.user).values_list('pk', flat=True)

    elif project and user:
        ssh_public_key_uuids = core_models.SshPublicKey.objects.filter(
            user=user).values_list('uuid', flat=True)
        membership_pks = CloudProjectMembership.objects.filter(
            project=project).values_list('pk', flat=True)

    if ssh_public_key_uuids and membership_pks:
        send_task('iaas', task_name)(list(ssh_public_key_uuids), list(membership_pks))


def propagate_new_users_key_to_his_projects_clouds(sender, instance=None, created=False, **kwargs):
    if created:
        sync_ssh_public_keys('push_ssh_public_keys', public_key=instance)


def remove_stale_users_key_from_his_projects_clouds(sender, instance=None, **kwargs):
    sync_ssh_public_keys('remove_ssh_public_keys', public_key=instance)


def propagate_users_keys_to_clouds_of_newly_granted_project(sender, structure, user, role, **kwargs):
    sync_ssh_public_keys('push_ssh_public_keys', project=structure, user=user)


def remove_stale_users_keys_from_clouds_of_revoked_project(sender, structure, user, role, **kwargs):
    sync_ssh_public_keys('remove_ssh_public_keys', project=structure, user=user)


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


change_customer_nc_instances_quota = quotas_handlers.quantity_quota_handler_factory(
    path_to_quota_scope='cloud_project_membership.project.customer',
    quota_name='nc_resource_count',
)


def check_instance_name_update(sender, instance=None, created=False, **kwargs):
    if created:
        return

    old_name = instance._old_values['name']
    if old_name != instance.name:
        from nodeconductor.iaas.tasks.zabbix import zabbix_update_host_visible_name
        zabbix_update_host_visible_name.delay(instance.uuid.hex)
