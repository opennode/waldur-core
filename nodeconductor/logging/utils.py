from django.db import models as django_models

from nodeconductor.logging import log


def get_loggable_models():
    models = [m for m in django_models.get_models() if issubclass(m, log.LoggableMixin)]

    # Add subclasses of abstract loggable models (eg Service)
    for model in log.LoggableMixin.__subclasses__():
        if model._meta.abstract:
            models.extend(model.__subclasses__())

    return models
