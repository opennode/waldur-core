from __future__ import unicode_literals

from django.apps import AppConfig
from django.db.models import signals

from nodeconductor.template import handlers


class TemplateConfig(AppConfig):
    name = 'nodeconductor.template'
    verbose_name = 'NodeConductor Template'

    def ready(self):
        pass
