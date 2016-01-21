from __future__ import unicode_literals
import logging

from django.apps import apps
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models

from nodeconductor.iaas.models import SecurityGroup, SecurityGroupRule, CloudProjectMembership


logger = logging.getLogger(__name__)


def create_initial_security_groups(sender, instance=None, created=False, **kwargs):
    if not created:
        return

    nc_settings = getattr(settings, 'NODECONDUCTOR', {})
    config_groups = nc_settings.get('DEFAULT_SECURITY_GROUPS', [])

    for group in config_groups:
        sg_name = group.get('name')
        if sg_name in (None, ''):
            logger.error('Skipping misconfigured security group: parameter "name" not found or is empty.')
            continue

        rules = group.get('rules')
        if type(rules) not in (list, tuple):
            logger.error('Skipping misconfigured security group: parameter "rules" should be list or tuple.')
            continue

        sg_description = group.get('description', None)
        sg = SecurityGroup.objects.get_or_create(
            cloud_project_membership=instance,
            description=sg_description,
            name=sg_name)[0]
        # Default security group will be created automatically. No need to push it for the first time.
        if sg_name == 'default':
            sg.state = 3
            sg.save()

        for rule in rules:
            if 'icmp_type' in rule:
                rule['from_port'] = rule.pop('icmp_type')
            if 'icmp_code' in rule:
                rule['to_port'] = rule.pop('icmp_code')

            try:
                rule = SecurityGroupRule(group=sg, **rule)
                rule.full_clean()
            except ValidationError as e:
                logger.error('Failed to create rule for security group %s: %s.' % (sg_name, e))
            else:
                rule.save()


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


def check_project_name_update(sender, instance=None, created=False, **kwargs):
    if created:
        return

    old_name = instance.tracker.previous('name')
    if old_name != instance.name:
        cpms = CloudProjectMembership.objects.filter(project__uuid=instance.uuid)
        if cpms.exists():
            from nodeconductor.iaas.tasks.zabbix import zabbix_update_host_visible_name
            from nodeconductor.iaas.tasks.iaas import update_cloud_project_membership_tenant_name

            for cpm in cpms:
                zabbix_update_host_visible_name.delay(cpm.pk, is_tenant=True)
                update_cloud_project_membership_tenant_name.delay(cpm.pk)
