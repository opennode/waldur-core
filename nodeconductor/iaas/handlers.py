from __future__ import unicode_literals

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.db import models

from nodeconductor.core.serializers import UnboundSerializerMethodField
from nodeconductor.core.tasks import send_task
from nodeconductor.structure.filters import filter_queryset_for_user


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


def create_initial_security_groups(sender, instance=None, created=False, **kwargs):
    if not created:
        return

    for group in instance.security_groups.model._get_default_security_groups():
        sg = instance.security_groups.create(
            name=group['name'],
            description=group['description'])

        for rule in group['rules']:
            sg.rules.create(**rule)

        send_task('iaas', 'create_security_group')(sg.uuid.hex)

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
