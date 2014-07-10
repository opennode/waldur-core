from django.contrib import admin

from nodeconductor.iaas import models


class InstanceAdmin(admin.ModelAdmin):
    readonly_fields = ('template', 'state')
    ordering = ('hostname',)


admin.site.register(models.Instance, InstanceAdmin)
admin.site.register(models.Template)
