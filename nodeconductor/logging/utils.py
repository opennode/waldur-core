from django.db import models as django_models

from nodeconductor.logging import log


def get_loggable_models():
    return [m for m in django_models.get_models() if issubclass(m, log.LoggableMixin)]
