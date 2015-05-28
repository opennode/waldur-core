from django.contrib.contenttypes import models as ct_models
from django.db import models as django_models

from nodeconductor.events import models, log


def get_loggable_models():
    return [m for m in django_models.get_models() if issubclass(m, log.EventLoggableMixin)]


def remove_related_alerts(sender, instance, **kwargs):
    content_type = ct_models.ContentType.objects.get_for_model(instance)
    for action in models.Alert .objects.filter(
            object_id=instance.id, content_type=content_type, closed__isnull=True).iterator():
        action.close()
