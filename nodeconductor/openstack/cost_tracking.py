from django.contrib.contenttypes.models import ContentType

from nodeconductor.cost_tracking import CostTrackingBackend
from nodeconductor.cost_tracking.models import DefaultPriceListItem
from nodeconductor.openstack import models, Types


class OpenStackCostTrackingBackend(CostTrackingBackend):
    NUMERICAL = [Types.PriceItems.STORAGE]
    STORAGE_KEY = '1 GB'

    @classmethod
    def get_default_price_list_items(cls):
        ct = ContentType.objects.get_for_model(models.Instance)
        price_item = lambda t, k: DefaultPriceListItem(item_type=t, key=k, resource_content_type=ct)

        # flavors
        for flavor in models.Flavor.objects.all():
            yield price_item(Types.PriceItems.FLAVOR, flavor.name)

        # os
        for os, _ in Types.Os.CHOICES:
            yield price_item(Types.PriceItems.LICENSE_OS, os)

        # applications
        for app, _ in Types.Applications.CHOICES:
            yield price_item(Types.PriceItems.LICENSE_APPLICATION, app)

        # support
        for support, _ in Types.Support.CHOICES:
            yield price_item(Types.PriceItems.SUPPORT, support)

        # storage
        yield price_item(Types.PriceItems.STORAGE, cls.STORAGE_KEY)

    @classmethod
    def get_monthly_cost_estimate(cls, resource):
        backend = resource.get_backend()
        return backend.get_monthly_cost_estimate(resource)

    @classmethod
    def get_used_items(cls, resource):
        items = []
        tags = [t.name for t in resource.tags.all()]

        def get_tag(name):
            try:
                return [t.split(':')[1] for t in tags if t.startswith('%s:' % name)][0]
            except IndexError:
                return None

        # flavor
        if resource.state == resource.States.ONLINE and resource.flavor_name:
            items.append((Types.PriceItems.FLAVOR, resource.flavor_name, 1))

        # OS
        os_type = get_tag(Types.PriceItems.LICENSE_OS)
        if os_type:
            items.append((Types.PriceItems.LICENSE_OS, os_type, 1))

        # application
        app_type = get_tag(Types.PriceItems.LICENSE_APPLICATION)
        if app_type:
            items.append((Types.PriceItems.LICENSE_APPLICATION, app_type, 1))

        # support
        support = get_tag(Types.PriceItems.SUPPORT)
        if support:
            items.append((Types.PriceItems.SUPPORT, support, 1))

        # storage
        storage_size = resource.data_volume_size
        storage_size += sum(b.metadata['system_snapshot_size'] +
                            b.metadata['data_snapshot_size'] for b in resource.backups.get_active())
        items.append((Types.PriceItems.STORAGE, cls.STORAGE_KEY, storage_size))

        return items
