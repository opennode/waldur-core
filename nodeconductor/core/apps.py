from __future__ import unicode_literals

from django.apps import AppConfig
from django.db.models import signals
from django.contrib.auth import get_user_model

from nodeconductor.core import handlers


class CoreConfig(AppConfig):
    name = 'nodeconductor.core'
    verbose_name = "NodeConductor Core"

    def ready(self):
        User = get_user_model()

        signals.post_save.connect(
            handlers.create_auth_token,
            sender=User,
            dispatch_uid='nodeconductor.core.handlers.create_auth_token',
        )

        signals.pre_save.connect(
            handlers.preserve_fields_before_update,
            sender=User,
            dispatch_uid='nodeconductor.core.handlers.preserve_fields_before_update',
        )

        signals.post_save.connect(
            handlers.log_user_save,
            sender=User,
            dispatch_uid='nodeconductor.core.handlers.log_user_save',
        )

        signals.post_delete.connect(
            handlers.log_user_delete,
            sender=User,
            dispatch_uid='nodeconductor.core.handlers.log_user_delete',
        )
