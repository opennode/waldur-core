import json

from django import forms
from django.contrib import admin

from nodeconductor.logging.models import Alert, SystemNotification
from nodeconductor.logging.loggers import get_valid_events


class JSONMultipleChoiceField(forms.MultipleChoiceField):

    def prepare_value(self, value):
        if isinstance(value, basestring):
            return json.loads(value)
        return value


class SystemNotificationForm(forms.ModelForm):
    event_types = JSONMultipleChoiceField(
        choices=[(e, e) for e in get_valid_events()],
        widget=forms.SelectMultiple(attrs={'size': '30'}))

    class Meta:
        model = SystemNotification
        exclude = 'uuid',


class SystemNotificationAdmin(admin.ModelAdmin):
    form = SystemNotificationForm
    list_display = 'hook_content_type',


class AlertAdmin(admin.ModelAdmin):
    list_display = ('uuid', 'alert_type', 'created', 'closed', 'scope', 'severity')
    list_filter = ('alert_type', 'created', 'closed', 'severity')
    ordering = ('alert_type',)
    base_model = Alert


admin.site.register(Alert, AlertAdmin)
admin.site.register(SystemNotification, SystemNotificationAdmin)
