import json

from django import forms
from django.contrib import admin

from nodeconductor.logging import models
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
        model = models.SystemNotification
        exclude = 'uuid',


class SystemNotificationAdmin(admin.ModelAdmin):
    form = SystemNotificationForm
    list_display = 'hook_content_type',


class AlertAdmin(admin.ModelAdmin):
    list_display = ('uuid', 'alert_type', 'created', 'closed', 'scope', 'severity')
    list_filter = ('alert_type', 'created', 'closed', 'severity')
    ordering = ('alert_type',)
    base_model = models.Alert


class BaseHookAdmin(admin.ModelAdmin):
    list_display = ('uuid', 'user', 'is_active', 'event_types', 'event_groups')


class WebHookAdmin(BaseHookAdmin):
    list_display = BaseHookAdmin.list_display + ('destination_url',)


class EmailHookAdmin(BaseHookAdmin):
    list_display = BaseHookAdmin.list_display + ('email',)


class PushHookAdmin(BaseHookAdmin):
    list_display = BaseHookAdmin.list_display + ('type', 'device_id')


admin.site.register(models.Alert, AlertAdmin)
admin.site.register(models.SystemNotification, SystemNotificationAdmin)
admin.site.register(models.WebHook, WebHookAdmin)
admin.site.register(models.EmailHook, EmailHookAdmin)
admin.site.register(models.PushHook, PushHookAdmin)
