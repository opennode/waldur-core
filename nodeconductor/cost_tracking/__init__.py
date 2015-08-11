import pkg_resources

from django.utils.lru_cache import lru_cache


default_app_config = 'nodeconductor.cost_tracking.apps.CostTrackingConfig'


class PriceItemTypes(object):
    FLAVOR = 'flavor'
    STORAGE = 'storage'
    LICENSE_APPLICATION = 'license-application'
    LICENSE_OS = 'license-os'
    SUPPORT = 'support'
    NETWORK = 'network'

    CHOICES = (
        (FLAVOR, 'flavor'),
        (STORAGE, 'storage'),
        (LICENSE_APPLICATION, 'license-application'),
        (LICENSE_OS, 'license-os'),
        (SUPPORT, 'support'),
        (NETWORK, 'network'),
    )


class OsTypes(object):
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


class ApplicationTypes(object):
    WORDPRESS = 'wordpress'
    POSTGRESQL = 'postgresql'
    ZIMBRA = 'zimbra'
    NONE = 'none'

    CHOICES = (
        (WORDPRESS, 'WordPress'),
        (POSTGRESQL, 'PostgreSQL'),
        (ZIMBRA, 'Zimbra'),
        (NONE, 'None'),
    )


class SupportTypes(object):
    BASIC = 'basic'
    PREMIUM = 'premium'

    CHOICES = (
        (BASIC, 'Basic'),
        (PREMIUM, 'Premium'),
    )


class CostConstants(object):
    PriceItem = PriceItemTypes
    Application = ApplicationTypes
    Os = OsTypes
    Support = SupportTypes

    class Flavor(object):
        OFFLINE = 'offline'


class CostTrackingStrategy(object):
    """ A parent class for the model-specific cost tracking strategies. """

    @classmethod
    def get_costs_estimates(cls):
        """ Get a list of estimated costs for the current year/month
            Should return a list of tuples in a form: (entity_obj, monthly_cost)

            Example:

            .. code-block:: python

                for droplet in Droplet.objects.all():
                    yield droplet, droplet.get_cost_estimate()

                yield droplet.service_project_link.service.customer, 0.99

        """
        raise NotImplementedError('Implement get_costs_estimates()')


@lru_cache(maxsize=1)
def get_cost_tracking_models():
    return [m.load() for m in pkg_resources.iter_entry_points('cost_tracking_strategies')]
