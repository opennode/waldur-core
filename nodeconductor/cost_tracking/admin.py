from django.conf.urls import patterns, url
from django.contrib import admin, messages
from django.contrib.admin import SimpleListFilter
from django.contrib.contenttypes.models import ContentType
from django.core.urlresolvers import reverse
from django.db import transaction
from django.shortcuts import redirect
from django.utils.translation import ungettext, gettext

from nodeconductor.core import NodeConductorExtension
from nodeconductor.core.tasks import send_task
from nodeconductor.cost_tracking import models, CostTrackingRegister
from nodeconductor.structure import SupportedServices
from nodeconductor.structure import models as structure_models, admin as structure_admin


def _get_content_type_queryset(models_list):
    """ Get list of services content types """
    content_type_ids = {c.id for c in ContentType.objects.get_for_models(*models_list).values()}
    return ContentType.objects.filter(id__in=content_type_ids)


class PriceListItemAdmin(admin.ModelAdmin):
    list_display = ('uuid', 'item_type', 'key', 'value', 'units', 'service')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "content_type":
            kwargs["queryset"] = _get_content_type_queryset(structure_models.Service.get_all_models())
        return super(PriceListItemAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)


class ResourceTypeFilter(SimpleListFilter):
    title = 'resource_type'
    parameter_name = 'resource_type'

    def lookups(self, request, model_admin):
        return [(k, k) for k in SupportedServices.get_resource_models().keys()]

    def queryset(self, request, queryset):
        if self.value():
            model = SupportedServices.get_resource_models().get(self.value(), None)
            if model:
                return queryset.filter(resource_content_type=ContentType.objects.get_for_model(model))
        return queryset


class DefaultPriceListItemAdmin(structure_admin.ChangeReadonlyMixin, admin.ModelAdmin):
    list_display = ('full_name', 'item_type', 'key', 'value', 'monthly_rate', 'resource_type')
    list_filter = ('item_type', ResourceTypeFilter)
    fields = ('name', ('value', 'monthly_rate'), 'resource_content_type', ('item_type', 'key'))
    readonly_fields = ('monthly_rate',)
    change_readonly_fields = ('resource_content_type', 'item_type', 'key')

    def full_name(self, obj):
        return obj.name or obj.units or obj.uuid

    def resource_type(self, obj):
        return SupportedServices.get_name_for_model(obj.resource_content_type.model_class())

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "resource_content_type":
            kwargs["queryset"] = _get_content_type_queryset(structure_models.Resource.get_all_models())
        return super(DefaultPriceListItemAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)

    def get_urls(self):
        my_urls = patterns(
            '',
            url(r'^sync/$', self.admin_site.admin_view(self.sync)),
            url(r'^subscribe_resources/$', self.admin_site.admin_view(self.subscribe_resources)),
            url(r'^init_from_registered_applications/$',
                self.admin_site.admin_view(self.init_from_registered_applications)),
        )
        return my_urls + super(DefaultPriceListItemAdmin, self).get_urls()

    def sync(self, request):
        # XXX: This code provides circular dependency between nodeconductor and nodeconductor-killbill
        if NodeConductorExtension.is_installed('nodeconductor_killbill'):
            send_task('killbill', 'sync_pricelist')()
            self.message_user(request, "Price lists scheduled for sync")
        else:
            self.message_user(request, "Unknown billing backend. Can't sync", level=messages.ERROR)

        return redirect(reverse('admin:cost_tracking_defaultpricelistitem_changelist'))

    def subscribe_resources(self, request):
        if NodeConductorExtension.is_installed('nodeconductor_killbill'):
            from nodeconductor_killbill.backend import KillBillBackend, KillBillError

            erred_resources = []
            subscribed_resources = []
            for model in structure_models.PaidResource.get_all_models():
                for resource in model.objects.exclude(state=model.States.ERRED):
                    try:
                        backend = KillBillBackend(resource.customer)
                        backend.subscribe(resource)
                    except KillBillError:
                        erred_resources.append(resource)
                    else:
                        resource.last_usage_update_time = None
                        resource.save(update_fields=['last_usage_update_time'])
                        subscribed_resources.append(resource)

            if subscribed_resources:
                subscribed_resources_count = len(subscribed_resources)
                message = ungettext(
                    'One resource subscribed',
                    '%(subscribed_resources_count)d resources subscribed',
                    subscribed_resources_count
                )
                message = message % {'subscribed_resources_count': subscribed_resources_count}
                self.message_user(request, message)

            if erred_resources:
                message = gettext('Failed to subscribe resources: %(erred_resources)s')
                message = message % {'erred_resources': ', '.join([i.name for i in erred_resources])}
                self.message_user(request, message, level=messages.ERROR)

        else:
            self.message_user(request, "Unknown billing backend. Can't sync", level=messages.ERROR)

        return redirect(reverse('admin:cost_tracking_defaultpricelistitem_changelist'))

    def init_from_registered_applications(self, request):
        created_items = []
        for backend in CostTrackingRegister.get_registered_backends():
            try:
                items = backend.get_default_price_list_items()
            except NotImplementedError:
                continue
            with transaction.atomic():
                for item in items:
                    item, created = models.DefaultPriceListItem.objects.update_or_create(
                        resource_content_type=item.resource_content_type,
                        item_type=item.item_type,
                        key=item.key,
                        defaults={
                            'value': item.value,
                            'name': '{}: {}'.format(item.item_type, item.key),
                            'metadata': item.metadata,
                            'units': item.units
                        }
                    )
                    if created:
                        created_items.append(item)
        if created_items:
            message = ungettext(
                'Price item was created: {}'.format(created_items[0].name),
                'Price items were created: {}'.format(', '.join(item.name for item in created_items)),
                len(created_items)
            )
            self.message_user(request, message)
        else:
            self.message_user(request, "Price items for all registered applications have been updated")

        return redirect(reverse('admin:cost_tracking_defaultpricelistitem_changelist'))


class PriceEstimateAdmin(admin.ModelAdmin):
    fields = ('content_type', 'object_id', 'total',
              ('month', 'year'), ('is_manually_input', 'is_visible'))
    list_display = ('content_type', 'object_id', 'total', 'month', 'year')
    list_filter = ('is_manually_input', 'is_visible')
    search_fields = ('month', 'year', 'object_id', 'total')


class ApplicationTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}

# TODO: disabled to reduce confusion. Enable once we start using it.
# admin.site.register(models.PriceListItem, PriceListItemAdmin)
admin.site.register(models.DefaultPriceListItem, DefaultPriceListItemAdmin)
admin.site.register(models.PriceEstimate, PriceEstimateAdmin)
admin.site.register(models.ApplicationType, ApplicationTypeAdmin)
