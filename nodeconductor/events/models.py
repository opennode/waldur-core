from django.contrib.contenttypes import fields as ct_fields
from django.contrib.contenttypes import models as ct_models
from django.db import models
from django.utils import timezone
from jsonfield import JSONField
from model_utils.models import TimeStampedModel


class Alert(TimeStampedModel):

    class SeverityChoices(object):
        DEBUG = 10
        INFO = 20
        WARNING = 30
        ERROR = 40
        choices = (('Debug', DEBUG), ('Info', INFO), ('Debug', WARNING), ('Error', ERROR),)

    alert_type = models.CharField(max_length=50)
    message = models.CharField(max_length=255)
    severity = models.SmallIntegerField(choices=SeverityChoices.choices)
    closed = models.DateTimeField(null=True, blank=True)
    context = JSONField(blank=True)

    content_type = models.ForeignKey(ct_models.ContentType, null=True, on_delete=models.SET_NULL)
    object_id = models.PositiveIntegerField(null=True)
    scope = ct_fields.GenericForeignKey('content_type', 'object_id')

    def close(self):
        self.closed = timezone.now()
        self.save()
