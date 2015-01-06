from __future__ import unicode_literals

from django.apps import AppConfig
from django.db.models import signals

from nodeconductor.iaas import handlers


class IaaSConfig(AppConfig):
    name = 'nodeconductor.iaas'
    verbose_name = "NodeConductor IaaS"

    # See, https://docs.djangoproject.com/en/1.7/ref/applications/#django.apps.AppConfig.ready
    def ready(self):
        Instance = self.get_model('Instance')

        # protect against a deletion of the Instance with connected backups
        # TODO: introduces dependency of IaaS on Backups, should be reconsidered
        signals.pre_delete.connect(
            handlers.prevent_deletion_of_instances_with_connected_backups,
            sender=Instance,
            dispatch_uid='nodeconductor.iaas.handlers.prevent_deletion_of_instances_with_connected_backups',
        )
