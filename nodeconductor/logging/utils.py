from django.apps import apps

from nodeconductor.logging.log import LoggableMixin


def get_loggable_models():
    return [model for model in apps.get_models() if issubclass(model, LoggableMixin)]
