from django.contrib import admin

from nodeconductor.cost_tracking import models


class ResourcePriceItemInline(admin.TabularInline):
    model = models.ResourcePriceItem
    extra = 0
    # TODO: Make inline output more readable


class PriceListItemAdmin(admin.ModelAdmin):
    inlines = (
        ResourcePriceItemInline,
    )
    list_display = ('uuid', 'key', 'item_type', 'value', 'units', 'service')
    readonly_fields = ('key', 'item_type', 'service')


class DefaultPriceListItemAdmin(admin.ModelAdmin):
    list_display = ('uuid', 'key', 'item_type', 'value', 'units', 'service_content_type')
    readonly_fields = ('key', 'item_type', 'service_content_type', 'is_manually_input')


admin.site.register(models.PriceListItem, PriceListItemAdmin)
admin.site.register(models.DefaultPriceListItem, DefaultPriceListItemAdmin)
