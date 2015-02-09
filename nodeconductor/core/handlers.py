from __future__ import unicode_literals

import logging

from nodeconductor.core.log import EventLoggerAdapter


logger = logging.getLogger(__name__)
event_logger = EventLoggerAdapter(logger)


def check_user_updated(sender, instance, **kwargs):
    if instance.id:
        obj = instance.__class__.objects.get(id=instance.id)
        setattr(instance, 'old_password', obj.password)
        setattr(instance, 'old_is_active', obj.is_active)


def log_user_save(sender, instance, created=False, **kwargs):
    if created:
        event_logger.info(
            'User %s has been created.', instance.username,
            extra={'affected_user': instance, 'event_type': 'user_created'})
    else:
        pwd_changed = hasattr(instance, 'old_password') and instance.old_password != instance.password
        act_changed = hasattr(instance, 'old_is_active') and instance.old_is_active != instance.is_active
        if pwd_changed or act_changed:
            if pwd_changed:
                event_logger.info(
                    'Password has been changed for user %s.', instance.username,
                    extra={'affected_user': instance, 'event_type': 'user_password_updated'})
            if act_changed:
                if instance.is_active:
                    event_logger.info(
                        'User %s has been activated.', instance.username,
                        extra={'affected_user': instance, 'event_type': 'user_activated'})
                else:
                    event_logger.info(
                        'User %s has been deactivated.', instance.username,
                        extra={'affected_user': instance, 'event_type': 'user_deactivated'})
        else:
            event_logger.info(
                'User %s has been updated.', instance.username,
                extra={'affected_user': instance, 'event_type': 'user_updated'})


def log_user_delete(sender, instance, **kwargs):
    event_logger.info(
        'User %s has been deleted.', instance.username,
        extra={'affected_user': instance, 'event_type': 'user_deleted'})
