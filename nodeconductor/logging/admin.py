from django.contrib import admin

from nodeconductor.logging import models


class AlertAdmin(admin.ModelAdmin):
    list_display = ('uuid', 'alert_type', 'closed', 'scope', 'severity')
    ordering = ('alert_type',)
    base_model = models.Alert

admin.site.register(models.Alert, AlertAdmin)
