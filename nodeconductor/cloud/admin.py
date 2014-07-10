from django.contrib import admin

from nodeconductor.cloud import models


class FlavorInline(admin.TabularInline):
    model = models.Flavor
    extra = 1


class CloudAdmin(admin.ModelAdmin):
    inlines = (
        FlavorInline,
    )
    list_display = ('name', 'organisation')
    ordering = ('name', 'organisation')


admin.site.register(models.OpenStackCloud, CloudAdmin)
