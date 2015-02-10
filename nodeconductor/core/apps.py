from __future__ import unicode_literals

from django.apps import AppConfig
from django.db.models import signals

from nodeconductor.core import handlers


class CoreConfig(AppConfig):
    name = 'nodeconductor.core'
    verbose_name = "NodeConductor Core"

    def ready(self):
        SshPublicKey = self.get_model('SshPublicKey')

        signals.post_save.connect(
            handlers.log_ssh_key_save,
            sender=SshPublicKey,
            dispatch_uid='nodeconductor.core.handlers.log_ssh_key_save',
        )

        signals.post_delete.connect(
            handlers.log_ssh_key_delete,
            sender=SshPublicKey,
            dispatch_uid='nodeconductor.core.handlers.log_ssh_key_delete',
        )
