from django.contrib import admin

from nodeconductor.iaas import models


class FlavorInline(admin.TabularInline):
    model = models.Flavor
    extra = 1


class CloudAdmin(admin.ModelAdmin):
    inlines = (
        FlavorInline,
    )
    list_display = ('name', 'organisation')
    ordering = ('name', 'organisation')


class InstanceAdmin(admin.ModelAdmin):
    readonly_fields = ('template', 'state')
    ordering = ('hostname',)


admin.site.register(models.Cloud, CloudAdmin)
admin.site.register(models.Instance, InstanceAdmin)
admin.site.register(models.Template)
