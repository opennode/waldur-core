from django.contrib import admin

from nodeconductor.logging import models


class AlertAdmin(admin.ModelAdmin):
    list_display = ('uuid', 'alert_type', 'created', 'closed', 'scope', 'severity')
    list_filter = ('alert_type', 'created', 'closed', 'severity')
    ordering = ('alert_type',)
    base_model = models.Alert

admin.site.register(models.Alert, AlertAdmin)
