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


class TemplateMappingInline(admin.TabularInline):
    model = models.TemplateMapping
    fields = ('description', 'backend_id')
    ordering = ('description', )
    extra = 3


class TemplateAdmin(admin.ModelAdmin):
    inlines = (
        TemplateMappingInline,
    )
    ordering = ('name', )


admin.site.register(models.Instance, InstanceAdmin)
admin.site.register(models.Template, TemplateAdmin)
admin.site.register(models.Image)
admin.site.register(models.Purchase, PurchaseAdmin)
