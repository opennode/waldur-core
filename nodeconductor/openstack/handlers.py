from __future__ import unicode_literals
import logging

from django.conf import settings
from django.core.exceptions import ValidationError

from nodeconductor.openstack.models import SecurityGroup, SecurityGroupRule, OpenStackServiceProjectLink


logger = logging.getLogger(__name__)


def set_spl_default_availability_zone(sender, instance=None, **kwargs):
    if not instance.availability_zone:
        settings = instance.service.settings
        if settings.options:
            instance.availability_zone = settings.options.get('availability_zone', '')


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
            service_project_link=instance,
            description=sg_description,
            name=sg_name)[0]

        for rule in rules:
            if 'icmp_type' in rule:
                rule['from_port'] = rule.pop('icmp_type')
            if 'icmp_code' in rule:
                rule['to_port'] = rule.pop('icmp_code')

            try:
                rule = SecurityGroupRule(security_group=sg, **rule)
                rule.full_clean()
            except ValidationError as e:
                logger.error('Failed to create rule for security group %s: %s.' % (sg_name, e))
            else:
                rule.save()


def increase_quotas_usage_on_instance_creation(sender, instance=None, created=False, **kwargs):
    add_quota = instance.service_project_link.add_quota_usage
    if created:
        add_quota('instances', 1)
        add_quota('ram', instance.ram)
        add_quota('vcpu', instance.cores)
        add_quota('storage', instance.disk)
    else:
        add_quota('ram', instance.ram - instance.tracker.previous('ram'))
        add_quota('vcpu', instance.cores - instance.tracker.previous('cores'))
        add_quota('storage', instance.disk - instance.tracker.previous('disk'))


def decrease_quotas_usage_on_instances_deletion(sender, instance=None, **kwargs):
    add_quota = instance.service_project_link.add_quota_usage
    add_quota('instances', -1)
    add_quota('ram', -instance.ram)
    add_quota('vcpu', -instance.cores)
    add_quota('storage', -instance.disk)


def change_floating_ip_quota_on_status_change(sender, instance, created=False, **kwargs):
    floating_ip = instance
    if floating_ip.status != 'DOWN' and (created or floating_ip.tracker.previous('status') == 'DOWN'):
        floating_ip.service_project_link.add_quota_usage('floating_ip_count', 1)
    if floating_ip.status == 'DOWN' and not created and floating_ip.tracker.previous('status') != 'DOWN':
        floating_ip.service_project_link.add_quota_usage('floating_ip_count', -1)


def check_project_name_update(sender, instance=None, created=False, **kwargs):
    if created:
        return

    old_name = instance.tracker.previous('name')
    if old_name != instance.name:
        links = OpenStackServiceProjectLink.objects.filter(project__uuid=instance.uuid)
        if links.exists():
            from nodeconductor.openstack.tasks import openstack_update_tenant_name

            for link in links:
                openstack_update_tenant_name.delay(link.to_string())
