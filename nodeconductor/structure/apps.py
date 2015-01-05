from __future__ import unicode_literals

from django.apps import AppConfig
from django.db.models import signals

from nodeconductor.structure import handlers


class StructureConfig(AppConfig):
    name = 'nodeconductor.structure'
    verbose_name = "NodeConductor Structure"

    # See, https://docs.djangoproject.com/en/1.7/ref/applications/#django.apps.AppConfig.ready
    def ready(self):
        ProjectGroup = self.get_model('ProjectGroup')

        signals.pre_delete.connect(
            handlers.prevent_non_empty_project_group_deletion,
            sender=ProjectGroup,
            dispatch_uid='nodeconductor.structure.handlers.prevent_non_empty_project_group_deletion',
        )
