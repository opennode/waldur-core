from __future__ import unicode_literals

import uuid

from django.conf import settings
from django.contrib.contenttypes import fields as ct_fields
from django.contrib.contenttypes import models as ct_models
from django.core.mail import send_mail
from django.db import models
from django.template.loader import render_to_string
from django.utils.lru_cache import lru_cache
from django.utils import timezone
from jsonfield import JSONField
from model_utils.models import TimeStampedModel
import requests
from uuidfield import UUIDField

from nodeconductor.core.utils import timestamp_to_datetime
from nodeconductor.logging import managers


class UuidMixin(models.Model):
    # There is circular dependency between logging and core applications.
    # Core models are loggable. So we cannot use UUID mixin here.

    class Meta:
        abstract = True

    uuid = UUIDField(auto=True, unique=True)


class Alert(UuidMixin, TimeStampedModel):

    class Meta:
        unique_together = ("content_type", "object_id", "alert_type", "is_closed")

    class SeverityChoices(object):
        DEBUG = 10
        INFO = 20
        WARNING = 30
        ERROR = 40
        CHOICES = ((DEBUG, 'Debug'), (INFO, 'Info'), (WARNING, 'Warning'), (ERROR, 'Error'))

    alert_type = models.CharField(max_length=50, db_index=True)
    message = models.CharField(max_length=255)
    severity = models.SmallIntegerField(choices=SeverityChoices.CHOICES)
    closed = models.DateTimeField(null=True, blank=True)
    # Hack: This field stays blank until alert closing.
    #       After closing it gets unique value to avoid unique together constraint break.
    is_closed = models.CharField(blank=True, max_length=32)
    acknowledged = models.BooleanField(default=False)
    context = JSONField(blank=True)

    content_type = models.ForeignKey(ct_models.ContentType, null=True, on_delete=models.SET_NULL)
    object_id = models.PositiveIntegerField(null=True)
    scope = ct_fields.GenericForeignKey('content_type', 'object_id')

    objects = managers.AlertManager()

    def close(self):
        self.closed = timezone.now()
        self.is_closed = uuid.uuid4().hex
        self.save()

    def acknowledge(self):
        self.acknowledged = True
        self.save()

    def cancel_acknowledgment(self):
        self.acknowledged = False
        self.save()


class AlertThresholdMixin(models.Model):
    """
    It is expected that model has scope field.
    """
    class Meta(object):
        abstract = True

    threshold = models.FloatField(blank=True, null=True)

    def is_over_threshold(self):
        """
        If returned value is True, alert is generated.
        """
        raise NotImplementedError

    @classmethod
    @lru_cache(maxsize=1)
    def get_all_models(cls):
        from django.apps import apps
        return [model for model in apps.get_models() if issubclass(model, cls)]

    @classmethod
    def get_checkable_objects(cls):
        """
        It should return queryset of objects that should be checked.
        """
        return cls.objects.all()


class BaseHook(UuidMixin, TimeStampedModel):
    class Meta:
        abstract = True

    user = models.ForeignKey(settings.AUTH_USER_MODEL)
    event_types = JSONField('List of event types')
    is_active = models.BooleanField(default=True)

    # This timestamp would be updated periodically when event is sent via this hook
    last_published = models.DateTimeField(default=timezone.now)

    @property
    def all_event_types(self):
        self_types = set(self.event_types)
        try:
            hook_ct = ct_models.ContentType.objects.get_for_model(self)
            base_types = SystemNotification.objects.get(hook_content_type=hook_ct)
        except SystemNotification.DoesNotExist:
            return self_types
        else:
            return self_types | set(base_types.event_types)

    @classmethod
    def get_active_hooks(cls):
        return [obj for hook in cls.__subclasses__() for obj in hook.objects.filter(is_active=True)]


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

    def process(self, event):
        # encode event as JSON
        if self.content_type == WebHook.ContentTypeChoices.JSON:
            requests.post(self.destination_url, json=event, verify=False)

        # encode event as form
        elif self.content_type == WebHook.ContentTypeChoices.FORM:
            requests.post(self.destination_url, data=event, verify=False)


class PushHook(BaseHook):

    class Type:
        IOS = 1
        ANDROID = 2
        CHOICES = ((IOS, 'iOS'), (ANDROID, 'Android'))

    type = models.SmallIntegerField(choices=Type.CHOICES)
    registration_token = models.CharField(max_length=255, blank=True)

    def process(self, event):
        """ Send events as push notification via Google Cloud Messaging.
            Expected settings as follows:

                # https://developers.google.com/mobile/add
                NODECONDUCTOR['GOOGLE_API'] = {
                    'Android': {
                        'project_id': 'nc-android',
                        'server_key': 'AIzaSyA2_7UaVIxXfKeFvxTjQNZbrzkXG9OTCkg',
                    },
                    'iOS': {
                        'project_id': 'nc-ios',
                        'server_key': 'AIzaSyA34zlG_y5uHOe2FmcJKwfk2vG-3RW05vk',
                    }
                }
        """

        conf = settings.NODECONDUCTOR.get('GOOGLE_API') or {}
        keys = conf.get(dict(self.Type.CHOICES)[self.type])

        if not keys or not self.registration_token:
            return

        endpoint = 'https://gcm-http.googleapis.com/gcm/send'
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'key=%s' % keys['server_key'],
        }
        payload = {
            'to': self.registration_token,
            'data': event,
        }

        requests.post(endpoint, json=payload, headers=headers)


class EmailHook(BaseHook):
    email = models.EmailField(max_length=75)

    def process(self, event):
        subject = 'Notifications from NodeConductor'
        event['timestamp'] = timestamp_to_datetime(event['timestamp'])
        text_message = event['message']
        html_message = render_to_string('logging/email.html', {'events': [event]})
        send_mail(subject, text_message, settings.DEFAULT_FROM_EMAIL, [self.email], html_message=html_message)


class SystemNotification(models.Model):
    event_types = JSONField('List of event types')
    hook_content_type = models.OneToOneField(
        ct_models.ContentType, related_name='+',
        limit_choices_to=lambda: {'id__in': [
            ct.id for ct in ct_models.ContentType.objects.get_for_models(
                *BaseHook.__subclasses__()).values()]})
