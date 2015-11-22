from __future__ import unicode_literals

from nodeconductor.template.log import event_logger


def log_template_save(sender, instance, created=False, **kwargs):
    if created:
        event_logger.template.info(
            'Template {template_name} has been created.',
            event_type='template_creation_succeeded',
            event_context={'template': instance})
    else:
        event_logger.template.info(
            'Template {template_name} has been updated.',
            event_type='template_update_succeeded',
            event_context={'template': instance})


def log_template_delete(sender, instance, **kwargs):
    event_logger.template.info(
        'Template {template_name} has been deleted.',
        event_type='template_deletion_succeeded',
        event_context={'template': instance})


def log_template_service_save(sender, instance, created=False, **kwargs):
    if created:
        event_logger.template_service.info(
            'Template {template_service_name} has been created.',
            event_type='template_service_creation_succeeded',
            event_context={'template_service': instance})
    else:
        event_logger.template_service.info(
            'Template {template_service_name} has been updated.',
            event_type='template_service_update_succeeded',
            event_context={'template_service': instance})


def log_template_service_delete(sender, instance, **kwargs):
    event_logger.template_service.info(
        'Template {template_service_name} has been deleted.',
        event_type='template_service_deletion_succeeded',
        event_context={'template_service': instance})
