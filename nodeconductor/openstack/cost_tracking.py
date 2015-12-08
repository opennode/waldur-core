from collections import OrderedDict
from django.contrib.contenttypes.models import ContentType

from nodeconductor.cost_tracking import CostTrackingBackend
from nodeconductor.cost_tracking.models import DefaultPriceListItem
from nodeconductor.openstack import models


class PriceItemTypes:
    FLAVOR = 'flavor'
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


class OsTypes:
    CENTOS6 = 'centos6'
    CENTOS7 = 'centos7'
    UBUNTU = 'ubuntu'
    RHEL6 = 'rhel6'
    RHEL7 = 'rhel7'
    FREEBSD = 'freebsd'
    WINDOWS = 'windows'
    OTHER = 'other'

    CHOICES = (
        (CENTOS6, 'Centos 6'),
        (CENTOS7, 'Centos 7'),
        (UBUNTU, 'Ubuntu'),
        (RHEL6, 'RedHat 6'),
        (RHEL7, 'RedHat 7'),
        (FREEBSD, 'FreeBSD'),
        (WINDOWS, 'Windows'),
        (OTHER, 'Other'),
    )

    CATEGORIES = OrderedDict([
        ('Linux', (CENTOS6, CENTOS7, UBUNTU, RHEL6, RHEL7)),
        ('Windows', (WINDOWS,)),
        ('Other', (FREEBSD, OTHER)),
    ])


class ApplicationTypes:
    WORDPRESS = 'wordpress'
    POSTGRESQL = 'postgresql'
    ZIMBRA = 'zimbra'

    CHOICES = (
        (WORDPRESS, 'WordPress'),
        (POSTGRESQL, 'PostgreSQL'),
        (ZIMBRA, 'Zimbra'),
    )


class SupportTypes:
    BASIC = 'basic'
    PREMIUM = 'premium'

    CHOICES = (
        (BASIC, 'Basic'),
        (PREMIUM, 'Premium'),
    )


class Types:
    PriceItems = PriceItemTypes
    Applications = ApplicationTypes
    Support = SupportTypes
    Os = OsTypes


class OpenStackCostTrackingBackend(CostTrackingBackend):

    STORAGE_KEY = '1 GB'

    @classmethod
    def get_default_price_list_items(cls):
        ct = ContentType.objects.get_for_model(models.Instance)
        price_item = lambda t, k: DefaultPriceListItem(item_type=t, key=k, resource_content_type=ct)

        # flavors
        for flavor in models.Flavor.objects.all():
            yield price_item(PriceItemTypes.FLAVOR, flavor.name)

        # os
        for os, _ in OsTypes.CHOICES:
            yield price_item(PriceItemTypes.LICENSE_OS, os)

        # applications
        for app, _ in ApplicationTypes.CHOICES:
            yield price_item(PriceItemTypes.LICENSE_APPLICATION, app)

        # support
        for support, _ in SupportTypes.CHOICES:
            yield price_item(PriceItemTypes.SUPPORT, support)

        # storage
        yield price_item(PriceItemTypes.STORAGE, cls.STORAGE_KEY)

    @classmethod
    def get_monthly_cost_estimate(cls, resource):
        backend = resource.get_backend()
        return backend.get_monthly_cost_estimate(resource)

    @classmethod
    def get_used_items(cls, resource):
        items = []
        tags = [t.name for t in resource.tags.all()]
        get_tag = lambda name: [t.split(':')[1] for t in tags if t.startswith('%s:' % name)][0]

        # flavor
        if resource.state == resource.States.ONLINE and resource.flavor_name:
            items.append((PriceItemTypes.FLAVOR, resource.flavor_name, 1))

        # OS
        os_type = get_tag(PriceItemTypes.LICENSE_OS)
        if os_type:
            items.append((PriceItemTypes.LICENSE_OS, os_type, 1))

        # application
        app_type = get_tag(PriceItemTypes.LICENSE_APPLICATION)
        if app_type:
            items.append((PriceItemTypes.LICENSE_APPLICATION, app_type, 1))

        # support
        support = get_tag(PriceItemTypes.SUPPORT)
        if support:
            items.append((PriceItemTypes.SUPPORT, support, 1))

        # storage
        storage_size = resource.data_volume_size
        storage_size += sum(b.metadata['system_snapshot_size'] +
                            b.metadata['data_snapshot_size'] for b in resource.backups.get_active())
        items.append((PriceItemTypes.STORAGE, cls.STORAGE_KEY, storage_size))

        return items
