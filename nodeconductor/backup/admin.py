from django.contrib import admin

from nodeconductor.backup import models


class BackupAdmin(admin.ModelAdmin):
    readonly_fields = ('created_at', 'kept_until',)
    list_filter = ('uuid', 'state', 'content_type',)

    list_display = ('uuid', 'content_type', 'backup_source', 'state')


class BackupScheduleAdmin(admin.ModelAdmin):
    readonly_fields = ('next_trigger_at',)
    list_filter = ('is_active', 'content_type')

    list_display = ('uuid', 'next_trigger_at', 'is_active', 'backup_source', 'content_type')


admin.site.register(models.Backup, BackupAdmin)
admin.site.register(models.BackupSchedule, BackupScheduleAdmin)