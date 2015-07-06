from django.contrib.contenttypes import fields as ct_fields
from django.contrib.contenttypes import models as ct_models
from django.conf import settings
from django.db import models
from django.utils import timezone
from jsonfield import JSONField
from model_utils.models import TimeStampedModel
from uuidfield import UUIDField

from nodeconductor.logging import managers


class Alert(TimeStampedModel):

    class SeverityChoices(object):
        DEBUG = 10
        INFO = 20
        WARNING = 30
        ERROR = 40
        CHOICES = ((DEBUG, 'Debug'), (INFO, 'Info'), (WARNING, 'Warning'), (ERROR, 'Error'))

    # There is circular dependency between logging and core applications. Core not abstract models are loggable.
    # So we cannot use UUID mixin here
    uuid = UUIDField(auto=True, unique=True)
    alert_type = models.CharField(max_length=50)
    message = models.CharField(max_length=255)
    severity = models.SmallIntegerField(choices=SeverityChoices.CHOICES)
    closed = models.DateTimeField(null=True, blank=True)
    acknowledged = models.BooleanField(default=False)
    context = JSONField(blank=True)

    content_type = models.ForeignKey(ct_models.ContentType, null=True, on_delete=models.SET_NULL)
    object_id = models.PositiveIntegerField(null=True)
    scope = ct_fields.GenericForeignKey('content_type', 'object_id')

    objects = managers.AlertManager()

    def close(self):
        self.closed = timezone.now()
        self.save()

    def acknowledge(self):
        self.acknowledged = True
        self.save()

    def cancel_acknowledgment(self):
        self.acknowledged = False
        self.save()


class Hook(TimeStampedModel):
    SERVICES = (('web', 'web'), ('email', 'email'))

    uuid = UUIDField(auto=True, unique=True)
    is_active = models.BooleanField(default=True, blank=True)

    user = models.ForeignKey(settings.AUTH_USER_MODEL)
    events = JSONField('List of event types')

    name = models.CharField('Name of publishing service', max_length=50, choices=SERVICES)
    settings = JSONField('Settings of publishing service')
    last_published = models.DateTimeField(default=timezone.now, blank=True)
