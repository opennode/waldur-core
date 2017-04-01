from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.contrib.contenttypes.models import ContentType
from django.core.urlresolvers import reverse
from django.shortcuts import redirect
from django.utils.translation import ungettext
from django.utils.translation import ugettext_lazy as _

from nodeconductor.core import admin as core_admin, utils as core_utils
from nodeconductor.cost_tracking import models, CostTrackingRegister, ResourceNotRegisteredError, tasks
from nodeconductor.structure import SupportedServices
from nodeconductor.structure import models as structure_models, admin as structure_admin


def _get_content_type_queryset(models_list):
    """ Get list of services content types """
    content_type_ids = {c.id for c in ContentType.objects.get_for_models(*models_list).values()}
    return ContentType.objects.filter(id__in=content_type_ids)


class ResourceTypeFilter(SimpleListFilter):
    title = 'resource_type'
    parameter_name = 'resource_type'

    def lookups(self, request, model_admin):
        return [(name, name) for name, model in SupportedServices.get_resource_models().items()
                if model in CostTrackingRegister.registered_resources]

    def queryset(self, request, queryset):
        if self.value():
            model = SupportedServices.get_resource_models().get(self.value(), None)
            if model:
                return queryset.filter(resource_content_type=ContentType.objects.get_for_model(model))
        return queryset


class DefaultPriceListItemAdmin(core_admin.ExtraActionsMixin, structure_admin.ChangeReadonlyMixin, admin.ModelAdmin):
    list_display = ('full_name', 'item_type', 'key', 'value', 'monthly_rate', 'resource_type')
    list_filter = ('item_type', ResourceTypeFilter)
    fields = ('name', ('value', 'monthly_rate'), 'resource_content_type', ('item_type', 'key'))
    readonly_fields = ('monthly_rate',)
    change_readonly_fields = ('resource_content_type', 'item_type', 'key')

    def full_name(self, obj):
        return obj.name or obj.units or obj.uuid

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "resource_content_type":
            kwargs["queryset"] = _get_content_type_queryset(CostTrackingRegister.registered_resources.keys())
        return super(DefaultPriceListItemAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)

    def get_extra_actions(self):
        return [
            self.init_from_registered_resources,
            self.delete_not_registered_items,
            self.recalulate_current_estimates,
        ]

    def init_from_registered_resources(self, request):
        """ Create default price list items for each registered resource. """
        created_items = models.DefaultPriceListItem.init_from_registered_resources()

        if created_items:
            message = ungettext(
                _('Price item was created: %s.') % created_items[0].name,
                _('Price items were created: %s.') % ', '.join(item.name for item in created_items),
                len(created_items)
            )
            self.message_user(request, message)
        else:
            self.message_user(request, _('Price items for all registered resources have been updated.'))

        return redirect(reverse('admin:cost_tracking_defaultpricelistitem_changelist'))

    def delete_not_registered_items(self, request):
        deleted_items_names = []

        for price_list_item in models.DefaultPriceListItem.objects.all():
            try:
                resource_class = price_list_item.resource_content_type.model_class()
                consumable_items = CostTrackingRegister.get_consumable_items(resource_class)
                next(item for item in consumable_items
                     if item.key == price_list_item.key and item.item_type == price_list_item.item_type)
            except (ResourceNotRegisteredError, StopIteration):
                deleted_items_names.append(price_list_item.name)
                price_list_item.delete()

        if deleted_items_names:
            message = ungettext(
                _('Price item was deleted: %s.') % deleted_items_names[0],
                _('Price items were deleted: %s.') % ', '.join(item for item in deleted_items_names),
                len(deleted_items_names)
            )
            self.message_user(request, message)
        else:
            self.message_user(request, _('Nothing to delete. All default price items are registered.'))

        return redirect(reverse('admin:cost_tracking_defaultpricelistitem_changelist'))

    def recalulate_current_estimates(self, request):
        tasks.recalculate_estimate(recalculate_total=True)
        self.message_user(request, _('Total and consumed value were successfully recalculated for all price estimates.'))
        return redirect(reverse('admin:cost_tracking_defaultpricelistitem_changelist'))


class PriceListItemAdmin(admin.ModelAdmin):
    list_display = ('uuid', 'default_price_list_item', 'service', 'units', 'value')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "content_type":
            kwargs["queryset"] = _get_content_type_queryset(structure_models.Service.get_all_models())
        return super(PriceListItemAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)


class ScopeTypeFilter(SimpleListFilter):
    title = 'resource_type'
    parameter_name = 'resource_type'

    def lookups(self, request, model_admin):
        resources = [(model, name) for name, model in SupportedServices.get_resource_models().items()]
        others = [(model, model.__name__) for model in models.PriceEstimate.get_estimated_models()
                  if not issubclass(model, structure_models.ResourceMixin)]
        estimated_models = [(core_utils.serialize_class(model), name) for model, name in resources + others]
        return sorted(estimated_models, key=lambda x: x[1])

    def queryset(self, request, queryset):
        if self.value():
            model = core_utils.deserialize_class(self.value())
            return queryset.filter(content_type=ContentType.objects.get_for_model(model))
        return queryset


class ConsumptionDetailsInline(admin.StackedInline):
    model = models.ConsumptionDetails
    readonly_fields = ('configuration', 'last_update_time', 'consumed_before_update')
    extra = 0
    can_delete = False


class PriceEstimateAdmin(admin.ModelAdmin):
    inlines = [ConsumptionDetailsInline]
    fields = ('content_type', 'object_id', ('total', 'consumed'), ('month', 'year'))
    list_display = ('content_type', 'object_id', 'total', 'month', 'year')
    list_filter = (ScopeTypeFilter, 'year', 'month')
    search_fields = ('month', 'year', 'object_id', 'total')


admin.site.register(models.DefaultPriceListItem, DefaultPriceListItemAdmin)
admin.site.register(models.PriceListItem, PriceListItemAdmin)
admin.site.register(models.PriceEstimate, PriceEstimateAdmin)
