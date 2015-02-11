from __future__ import unicode_literals

import logging

from rest_framework.authtoken.models import Token

from nodeconductor.core.log import EventLoggerAdapter


logger = logging.getLogger(__name__)
event_logger = EventLoggerAdapter(logger)


def create_auth_token(sender, instance, created=False, **kwargs):
    if created:
        Token.objects.create(user=instance)


def preserve_fields_before_update(sender, instance, **kwargs):
    if instance.pk is None:
        return

    old_instance = instance._meta.model._default_manager.get(pk=instance.pk)
    old_values = {
        field_name: getattr(old_instance, field_name)
        for field_name in instance._meta.get_all_field_names()
    }

    setattr(instance, '_old_values', old_values)


def log_user_save(sender, instance, created=False, **kwargs):
    if created:
        event_logger.info(
            'User %s has been created.', instance.username,
            extra={'affected_user': instance, 'event_type': 'user_creation_succeeded'})
    else:
        old_values = instance._old_values

        password_changed = instance.password != old_values['password']
        activation_changed = instance.is_active != old_values['is_active']
        user_updated = any(
            old_values[field_name] != getattr(instance, field_name)
            for field_name in instance._meta.get_all_field_names()
            if field_name not in ('password', 'is_active')
        )

        if password_changed:
            event_logger.info(
                'Password has been changed for user %s.', instance.username,
                extra={'affected_user': instance, 'event_type': 'user_password_updated'})

        if activation_changed:
            if instance.is_active:
                event_logger.info(
                    'User %s has been activated.', instance.username,
                    extra={'affected_user': instance, 'event_type': 'user_activated'})
            else:
                event_logger.info(
                    'User %s has been deactivated.', instance.username,
                    extra={'affected_user': instance, 'event_type': 'user_deactivated'})

        if user_updated:
            event_logger.info(
                'User %s has been updated.', instance.username,
                extra={'affected_user': instance, 'event_type': 'user_update_succeeded'})


def log_user_delete(sender, instance, **kwargs):
    event_logger.info(
        'User %s has been deleted.', instance.username,
        extra={'affected_user': instance, 'event_type': 'user_deletion_succeeded'})


def log_ssh_key_save(sender, instance, created=False, **kwargs):
    if created:
        event_logger.info(
            'SSH key %s has been created.', instance.name,
            extra={'ssh_key': instance, 'event_type': 'ssh_key_creation_succeeded'})


def log_ssh_key_delete(sender, instance, **kwargs):
    event_logger.info(
        'SSH key %s has been deleted.', instance.name,
        extra={'ssh_key': instance, 'event_type': 'ssh_key_deletion_succeeded'})
