from django.contrib import admin

from nodeconductor.iaas import models


class InstanceAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ['template', 'state', ]
        else:
            return ['state', ]
    ordering = ('hostname',)

admin.site.register(models.Instance, InstanceAdmin)
admin.site.register(models.Template)
