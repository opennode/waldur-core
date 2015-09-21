from django.conf.urls import patterns, url
from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.core.urlresolvers import reverse
from django.shortcuts import redirect
from django.utils.translation import ungettext

from nodeconductor.core.tasks import send_task
from nodeconductor.cost_tracking import models
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
            url(r'^create_for_flavors/$', self.admin_site.admin_view(self.create_for_flavors)),
        )
        return my_urls + super(DefaultPriceListItemAdmin, self).get_urls()

    def sync(self, request):
        send_task('billing', 'sync_pricelist')()
        self.message_user(request, "Pricelists scheduled for sync")
        return redirect(reverse('admin:cost_tracking_defaultpricelistitem_changelist'))

    def create_for_flavors(self, request):
        # XXX: this import creates circular dependency between iaas and cost_tracking applications:
        from nodeconductor.iaas.models import Instance, Flavor
        instance_content_type = ContentType.objects.get_for_model(Instance)
        executed_flavors = []
        for flavor in Flavor.objects.all():
            lookup_kwargs = {'item_type': 'flavor', 'key': flavor.name, 'resource_content_type': instance_content_type}
            if not models.DefaultPriceListItem.objects.filter(**lookup_kwargs).exists():
                item = models.DefaultPriceListItem(**lookup_kwargs)
                item.name = 'Flavor type: {}'.format(flavor.name)
                item.save()
                executed_flavors.append(flavor)

        if executed_flavors:
            message = ungettext(
                'Price item were created for flavor: {}'.format(executed_flavors[0].name),
                'Price items were created for flavors: {}'.format(', '.join(f.name for f in executed_flavors)),
                len(executed_flavors)
            )
            self.message_user(request, message)
        else:
            self.message_user(request, "Price items exist for all flavors")

        return redirect(reverse('admin:cost_tracking_defaultpricelistitem_changelist'))


class ApplicationTypeAdmin(admin.ModelAdmin):
    list_display = ('name', )


admin.site.register(models.PriceListItem, PriceListItemAdmin)
admin.site.register(models.DefaultPriceListItem, DefaultPriceListItemAdmin)
admin.site.register(models.PriceEstimate)
admin.site.register(models.ApplicationType, ApplicationTypeAdmin)
