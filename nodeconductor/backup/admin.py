import pytz

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms import ModelForm
from django.utils.translation import ugettext_lazy as _

from nodeconductor.backup import models


class BackupAdmin(admin.ModelAdmin):
    readonly_fields = ('created_at', 'kept_until',)
    list_filter = ('uuid', 'state', 'content_type',)

    list_display = ('uuid', 'content_type', 'backup_source', 'state')


class BackupScheduleForm(ModelForm):
    def clean_timezone(self):
        tz = self.cleaned_data['timezone']
        if tz not in pytz.all_timezones:
            raise ValidationError(_('Invalid timezone'), code='invalid')

        return self.cleaned_data['timezone']


class BackupScheduleAdmin(admin.ModelAdmin):
    form = BackupScheduleForm
    readonly_fields = ('next_trigger_at',)
    list_filter = ('is_active', 'content_type')

    list_display = ('uuid', 'next_trigger_at', 'is_active', 'backup_source', 'content_type', 'timezone')


admin.site.register(models.Backup, BackupAdmin)
admin.site.register(models.BackupSchedule, BackupScheduleAdmin)
