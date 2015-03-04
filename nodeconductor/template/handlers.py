from __future__ import unicode_literals

import logging

from nodeconductor.core.log import EventLoggerAdapter


logger = logging.getLogger(__name__)
event_logger = EventLoggerAdapter(logger)


def log_template_save(sender, instance, created=False, **kwargs):
    if created:
        event_logger.info(
            'Template %s has been created.', instance.name,
            extra={'template': instance, 'event_type': 'template_creation_succeeded'}
        )
    else:
        event_logger.info(
            'Template %s has been updated.', instance.name,
            extra={'template': instance, 'event_type': 'template_update_succeeded'}
        )


def log_template_delete(sender, instance, **kwargs):
    event_logger.info(
        'Template %s has been deleted.', instance.name,
        extra={'template': instance, 'event_type': 'template_deletion_succeeded'}
    )


def log_template_service_save(sender, instance, created=False, **kwargs):
    if created:
        event_logger.info(
            'Template service %s has been created.', instance.name,
            extra={'template_service': instance, 'event_type': 'template_service_creation_succeeded'}
        )
    else:
        event_logger.info(
            'Template service %s has been updated.', instance.name,
            extra={'template_service': instance, 'event_type': 'template_service_update_succeeded'}
        )


def log_template_service_delete(sender, instance, **kwargs):
    event_logger.info(
        'Template service %s has been deleted.', instance.name,
        extra={'template_service': instance, 'event_type': 'template_service_deletion_succeeded'}
    )
