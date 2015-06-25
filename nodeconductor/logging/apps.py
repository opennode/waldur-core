from __future__ import unicode_literals

from django.apps import AppConfig
from django.db.models import signals

from nodeconductor.logging import handlers, utils


class EventsConfig(AppConfig):
    name = 'nodeconductor.logging'
    verbose_name = 'NodeConductor Logging'

    def ready(self):
        for model in utils.get_loggable_models():
            signals.post_delete.connect(
                handlers.remove_related_alerts,
                sender=model,
                dispatch_uid='nodeconductor.logging.handlers.remove_%s_related_alerts' % model.__name__.lower(),
            )
