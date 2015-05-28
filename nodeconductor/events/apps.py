from __future__ import unicode_literals

from django.apps import AppConfig
from django.db.models import signals

from nodeconductor.events import handlers


class EventsConfig(AppConfig):
    name = 'nodeconductor.events'
    verbose_name = 'NodeConductor Events'

    def ready(self):
        for model in handlers.get_loggable_models():
            signals.post_delete.connect(
                handlers.remove_related_alerts,
                sender=model,
                dispatch_uid='nodeconductor.events.handlers.remove_%s_related_alerts' % model.__name__.lower(),
            )
