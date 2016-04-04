from __future__ import unicode_literals

from django.apps import AppConfig
from django.db.models import signals


class EventsConfig(AppConfig):
    name = 'nodeconductor.logging'
    verbose_name = 'Logging'

    def ready(self):
        from nodeconductor.logging import handlers, utils

        for index, model in enumerate(utils.get_loggable_models()):
            signals.post_delete.connect(
                handlers.remove_related_alerts,
                sender=model,
                dispatch_uid='nodeconductor.logging.handlers.remove_{}_{}_related_alerts'.format(model.__name__, index),
            )
