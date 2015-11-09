from django.conf.urls import patterns, url
from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.core.urlresolvers import reverse
from django.shortcuts import redirect
from django.utils.translation import ungettext

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


class DefaultPriceListItemAdmin(structure_admin.ChangeReadonlyMixin, admin.ModelAdmin):
    list_display = ('full_name', 'item_type', 'key', 'value', 'monthly_rate', 'product_name')
    list_filter = ['item_type', 'key']
    fields = ('name', ('value', 'monthly_rate'), 'resource_content_type', ('item_type', 'key'))
    readonly_fields = ('monthly_rate',)
    change_readonly_fields = ('resource_content_type', 'item_type', 'key')

    def full_name(self, obj):
        return obj.name or obj.units or obj.uuid

    def product_name(self, obj):
        return SupportedServices.get_name_for_model(
            obj.resource_content_type.model_class()).title().replace('.', '')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "resource_content_type":
            kwargs["queryset"] = _get_content_type_queryset(structure_models.Resource.get_all_models())
        return super(DefaultPriceListItemAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)

    def get_urls(self):
        my_urls = patterns(
            '',
            url(r'^sync/$', self.admin_site.admin_view(self.sync)),
            url(r'^init_from_registered_applications/$',
                self.admin_site.admin_view(self.init_from_registered_applications)),
        )
        return my_urls + super(DefaultPriceListItemAdmin, self).get_urls()

    def sync(self, request):
        send_task('billing', 'sync_pricelist')()
        self.message_user(request, "Price lists scheduled for sync")
        return redirect(reverse('admin:cost_tracking_defaultpricelistitem_changelist'))

    def init_from_registered_applications(self, request):
        created_items = []
        for backend in CostTrackingRegister.get_registered_backends():
            for item in backend.get_default_price_list_items():
                if not models.DefaultPriceListItem.objects.filter(resource_content_type=item.resource_content_type,
                                                                  item_type=item.item_type, key=item.key).exists():
                    if not item.name:
                        item.name = '{}: {}'.format(item.item_type, item.key)
                    item.save()
                    created_items.append(item)
        if created_items:
            message = ungettext(
                'Price item were created for key: {}'.format(created_items[0].key),
                'Price items were created for flavors: {}'.format(', '.join(item.key for item in created_items)),
                len(created_items)
            )
            self.message_user(request, message)
        else:
            self.message_user(request, "Price items exist for all registered applications")

        return redirect(reverse('admin:cost_tracking_defaultpricelistitem_changelist'))


class ApplicationTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


admin.site.register(models.PriceListItem, PriceListItemAdmin)
admin.site.register(models.DefaultPriceListItem, DefaultPriceListItemAdmin)
admin.site.register(models.PriceEstimate)
admin.site.register(models.ApplicationType, ApplicationTypeAdmin)
