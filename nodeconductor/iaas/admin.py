from django.contrib import admin

from nodeconductor.iaas import models


class InstanceAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ['template']
        return []
    ordering = ('hostname',)
    list_display = ['hostname', 'uuid', 'state', 'project', 'template', 'flavor']
    search_fields = ['hostname', 'uuid']
    list_filter = ['state', 'project', 'template']


class PurchaseAdmin(admin.ModelAdmin):
    readonly_fields = ('date', 'user', 'project')


admin.site.register(models.Instance, InstanceAdmin)
admin.site.register(models.Template)
admin.site.register(models.Image)
admin.site.register(models.Purchase, PurchaseAdmin)
