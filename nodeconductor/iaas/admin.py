from django.contrib import admin

from nodeconductor.iaas import models


# Inspired by Django Snippet https://djangosnippets.org/snippets/2629/
class ReadonlyInlineMixin(object):
    can_delete = False
    extra = 0

    def has_add_permission(self, request):
        return False


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


class ImageInline(ReadonlyInlineMixin, admin.TabularInline):
    model = models.Image
    fields = ('get_cloud_name', 'get_customer_name', 'backend_id')
    readonly_fields = ('get_cloud_name', 'get_customer_name', 'backend_id')
    ordering = ('cloud__name', 'cloud__customer__name')
    verbose_name_plural = 'Connected cloud images'

    def get_cloud_name(self, obj):
        return obj.cloud.name
    get_cloud_name.short_description = 'Cloud'

    def get_customer_name(self, obj):
        return obj.cloud.customer.name
    get_customer_name.short_description = 'Customer'


class TemplateMappingInline(admin.TabularInline):
    model = models.TemplateMapping
    fields = ('description', 'backend_image_id')
    ordering = ('description', )
    extra = 3


class TemplateAdmin(admin.ModelAdmin):
    inlines = (
        TemplateMappingInline,
        ImageInline,
    )
    ordering = ('name', )


admin.site.register(models.Instance, InstanceAdmin)
admin.site.register(models.Template, TemplateAdmin)
admin.site.register(models.Purchase, PurchaseAdmin)
