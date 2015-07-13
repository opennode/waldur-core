from django.contrib.contenttypes import fields as ct_fields
from django.contrib.contenttypes import models as ct_models
from django.core.mail import send_mail
from django.conf import settings
from django.db import models
from django.utils import timezone
from jsonfield import JSONField
from model_utils.models import TimeStampedModel
from uuidfield import UUIDField
import requests

from nodeconductor.logging import managers


class UuidMixin(models.Model):
    # There is circular dependency between logging and core applications. 
    # Core models are loggable. So we cannot use UUID mixin here.

    class Meta:
        abstract = True

    uuid = UUIDField(auto=True, unique=True)


class Alert(UuidMixin, TimeStampedModel):

    class SeverityChoices(object):
        DEBUG = 10
        INFO = 20
        WARNING = 30
        ERROR = 40
        CHOICES = ((DEBUG, 'Debug'), (INFO, 'Info'), (WARNING, 'Warning'), (ERROR, 'Error'))

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


class BaseHook(UuidMixin, TimeStampedModel):
    class Meta:
        abstract = True

    user = models.ForeignKey(settings.AUTH_USER_MODEL)
    event_types = JSONField('List of event types')
    is_active = models.BooleanField(default=True)

    # This timestamp would be updated periodically when event is sent via this hook
    last_published = models.DateTimeField(default=timezone.now)


def get_hook_models():
    return [m for m in models.get_models() if issubclass(m, BaseHook)]


class WebHook(BaseHook):
    class ContentTypeChoices(object):
        JSON = 1
        FORM = 2
        CHOICES = ((JSON, 'json'), (FORM, 'form'))

    destination_url = models.URLField()
    content_type = models.SmallIntegerField(
        choices=ContentTypeChoices.CHOICES,
        default=ContentTypeChoices.JSON
    )

    def process(self, events):
        for event in events:
            # encode event as JSON
            if self.content_type == WebHook.ContentTypeChoices.JSON:
                requests.post(self.destination_url, json=event, verify=False)

            # encode event as form
            elif self.content_type == WebHook.ContentTypeChoices.FORM:
                requests.post(self.destination_url, data=event, verify=False)


class EmailHook(BaseHook):
    email = models.EmailField()

    def process(self, events):
        subject = 'Notifications from NodeConductor'
        body = self.format_email_body(events)
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [self.email])

    def format_email_body(self, events):
        return "\n".join(event['message'] for event in events)
