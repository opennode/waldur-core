from django.contrib import admin

from nodeconductor.iaas import models


class InstanceAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ['template', 'state', ]
        else:
            return ['state', ]
    ordering = ('hostname',)


class PurchaseAdmin(admin.ModelAdmin):
    readonly_fields = ('date', 'user', 'project')


admin.site.register(models.Instance, InstanceAdmin)
admin.site.register(models.Template)
admin.site.register(models.Image)
admin.site.register(models.Purchase, PurchaseAdmin)
