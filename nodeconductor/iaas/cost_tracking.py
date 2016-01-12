from django.contrib.contenttypes.models import ContentType

from nodeconductor.cost_tracking import CostTrackingBackend
from nodeconductor.cost_tracking.models import DefaultPriceListItem, ApplicationType
from nodeconductor.iaas import models


class PriceItemTypes(object):
    FLAVOR = CostTrackingBackend.VM_SIZE_ITEM_TYPE
    STORAGE = 'storage'
    LICENSE_APPLICATION = 'license-application'
    LICENSE_OS = 'license-os'
    SUPPORT = 'support'

    CHOICES = (
        (FLAVOR, 'flavor'),
        (STORAGE, 'storage'),
        (LICENSE_APPLICATION, 'license-application'),
        (LICENSE_OS, 'license-os'),
        (SUPPORT, 'support'),
    )


# XXX: Support type should be moved to instance model
class SupportTypes(object):
    BASIC = 'basic'
    PREMIUM = 'premium'

    CHOICES = (
        (BASIC, 'Basic'),
        (PREMIUM, 'Premium'),
    )


class IaaSCostTrackingBackend(CostTrackingBackend):
    NUMERICAL = [PriceItemTypes.STORAGE]
    STORAGE_KEY = '1 GB'

    @classmethod
    def get_default_price_list_items(cls):
        instance_content_type = ContentType.objects.get_for_model(models.Instance)
        items = []
        # flavors
        for flavor in models.Flavor.objects.all():
            items.append(DefaultPriceListItem(
                item_type=PriceItemTypes.FLAVOR,
                key=flavor.name,
                resource_content_type=instance_content_type))
        # OS
        for os, _ in models.Template.OsTypes.CHOICES:
            items.append(DefaultPriceListItem(
                item_type=PriceItemTypes.LICENSE_OS, key=os, resource_content_type=instance_content_type))
        # applications
        for application_type in ApplicationType.objects.all():
            items.append(DefaultPriceListItem(
                item_type=PriceItemTypes.LICENSE_APPLICATION, key=application_type.slug,
                resource_content_type=instance_content_type))
        # storage
        items.append(DefaultPriceListItem(
            item_type=PriceItemTypes.STORAGE, key=cls.STORAGE_KEY, resource_content_type=instance_content_type))
        # support
        for support, _ in SupportTypes.CHOICES:
            items.append(DefaultPriceListItem(
                item_type=PriceItemTypes.SUPPORT, key=support, resource_content_type=instance_content_type))
        return items

    @classmethod
    def get_monthly_cost_estimate(cls, resource):
        # XXX: Implement cost estimate calculation in this method, remove dependency from billing application
        backend = resource.get_backend()
        return backend.get_monthly_cost_estimate(resource)

    @classmethod
    def get_used_items(cls, resource):
        items = []
        # flavor
        if resource.state == resource.States.ONLINE and resource.flavor_name:
            items.append((PriceItemTypes.FLAVOR, resource.flavor_name, 1))
        # OS
        items.append((PriceItemTypes.LICENSE_OS, resource.template.os_type, 1))
        # application
        application = resource.template.application_type
        if application:
            items.append((PriceItemTypes.LICENSE_APPLICATION, application.slug, 1))
        # storage
        storage_size = resource.data_volume_size
        storage_size += sum(b.metadata['system_snapshot_size'] +
                            b.metadata['data_snapshot_size'] for b in resource.backups.get_active())
        items.append((PriceItemTypes.STORAGE, cls.STORAGE_KEY, storage_size))
        # support
        support_name = SupportTypes.PREMIUM if resource.type == resource.Services.PAAS else SupportTypes.BASIC
        items.append((PriceItemTypes.SUPPORT, support_name, 1))
        return items
