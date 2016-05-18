# TODO: move this module code to itacloud assembly
""" Itacloud-specific operations that register Openstack instance in Zabbix """
import logging

from nodeconductor.structure import models as structure_models
from nodeconductor.template import settings


logger = logging.getLogger(__name__)


class ZabbixIntegrationError(Exception):
    pass

try:
    from nodeconductor_zabbix import models, executors
except ImportError:
    raise ZabbixIntegrationError('Module nodeconductor-zabbix should be installed for OpenStack-Zabbix integration')


def _get_settings():
    return structure_models.ServiceSettings.objects.get(name=settings.SHARED_ZABBIX_SETTINGS_NAME)


def _get_tag_prefix(tag):
    """ Extract tag prefix that does not contain user-friendly name """
    return ':'.join(tag.name.split(':')[:2])


def _get_instance_templates(instance):
    """ Get Zabbix templates based on instance tags """
    zabbix_settings = _get_settings()
    names = settings.DEFAULT_HOST_TEMPLATES
    for tag in instance.tags.all():
        tag_prefix = _get_tag_prefix(tag)
        if tag_prefix in settings.ADDITIONAL_HOST_TEMPLATES:
            names += settings.ADDITIONAL_HOST_TEMPLATES[tag_prefix]
    templates = models.Template.objects.filter(name__in=names, settings=zabbix_settings)
    # make sure that all templates from settings really exist in Zabbix
    if templates.count() != len(names):
        missing_templates = set(names) - set(templates.values_list('name', flat=True))
        raise ZabbixIntegrationError('There are not templates with name: %s' % ', '.join(missing_templates))
    return templates


def _get_instance_trigger(instance, host):
    zabbix_settings = _get_settings()
    name = settings.DEFAULT_SLA_TRIGGER_NAME
    for tag in instance.tags.all():
        tag_prefix = _get_tag_prefix(tag)
        if tag_prefix in settings.SLA_TRIGGER_NAMES:
            name = settings.SLA_TRIGGER_NAMES[tag_prefix]
            break
    try:
        return models.Trigger.objects.get(name=name, settings=zabbix_settings, template__in=host.templates.all())
    except models.Trigger.DoesNotExist:
        logger.error('Cannot find trigger with name `%s` in templates: %s',
                     name, ', '.join([t.name for t in host.templates.all()]))


def register_instance(instance):
    """ Create Zabbix host and IT Service for instance """
    if not instance.backend_id:
        raise ZabbixIntegrationError(
            'Cannot register OpenStack instance %s (PK: %s) - it does not have sabackend_id' % (instance, instance.pk))

    zabbix_settings = _get_settings()
    # get SPL that links instance project and defined Zabbix settings
    spl = models.ZabbixServiceProjectLink.objects.get(
        project=instance.service_project_link.project, service__settings=zabbix_settings)
    # create Zabbix Host based on itacloud settings
    host = models.Host.objects.create(
        scope=instance,
        service_project_link=spl,
        visible_name=instance.name,
        name=instance.backend_id,
        host_group_name=settings.HOST_GROUP_NAME,
    )
    templates = _get_instance_templates(instance)
    host.templates.add(*templates)
    executors.HostCreateExecutor.execute(host, async=False)
    # create Zabbix IT service based on itacloud settings
    trigger = _get_instance_trigger(instance, host)
    it_service = models.ITService.objects.create(
        name='Availability of %s' % host.name,
        host=host,
        is_main=True,
        service_project_link=spl,
        algorithm=models.ITService.Algorithm.ANY,
        agreed_sla=settings.AGREED_SLA,
        trigger=trigger,
    )
    executors.ITServiceCreateExecutor.execute(it_service, async=False)
