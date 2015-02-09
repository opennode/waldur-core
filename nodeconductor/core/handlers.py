from __future__ import unicode_literals

import logging

from nodeconductor.core.log import EventLoggerAdapter


logger = logging.getLogger(__name__)
event_logger = EventLoggerAdapter(logger)


def log_ssh_key_save(sender, instance, created=False, **kwargs):
    if created:
        event_logger.info(
            'SSH key %s has been created.', instance.name,
            extra={'ssh_key': instance, 'event_type': 'ssh_key_created'})


def log_ssh_key_delete(sender, instance, **kwargs):
    event_logger.info(
        'SSH key %s has been deleted.', instance.name,
        extra={'ssh_key': instance, 'event_type': 'ssh_key_deleted'})
