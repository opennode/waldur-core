from django.contrib import admin
from django.contrib.contenttypes.models import ContentType

from nodeconductor.cost_tracking import models
from nodeconductor.structure import models as structure_models


class PriceListItemAdmin(admin.ModelAdmin):
    list_display = ('uuid', 'key', 'item_type', 'value', 'units', 'service')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "content_type":
            services = structure_models.Service.get_all_models()
            service_content_type_ids = [ContentType.objects.get_for_model(s).id for s in services]
            kwargs["queryset"] = ContentType.objects.filter(id__in=service_content_type_ids)
        return super(PriceListItemAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)


class DefaultPriceListItemAdmin(admin.ModelAdmin):
    list_display = ('uuid', 'key', 'item_type', 'value', 'units', 'service_content_type')

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ['service_content_type']
        else:
            return []

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "service_content_type":
            services = structure_models.Service.get_all_models()
            service_content_type_ids = [ContentType.objects.get_for_model(s).id for s in services]
            kwargs["queryset"] = ContentType.objects.filter(id__in=service_content_type_ids)
        return super(DefaultPriceListItemAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)


admin.site.register(models.PriceListItem, PriceListItemAdmin)
admin.site.register(models.DefaultPriceListItem, DefaultPriceListItemAdmin)
