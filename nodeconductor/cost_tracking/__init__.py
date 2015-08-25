import types
import logging
import itertools
import pkg_resources

from django.utils.lru_cache import lru_cache

from nodeconductor.structure import ServiceBackendError, ServiceBackendNotImplemented


default_app_config = 'nodeconductor.cost_tracking.apps.CostTrackingConfig'
logger = logging.getLogger(__name__)


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

    CATEGORIES = {
        'linux': (CENTOS6, CENTOS7, UBUNTU, RHEL6, RHEL7)
    }


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


class CostTrackingStrategy(object):
    """ A base class for the model-specific cost tracking strategies.
        If 'RESOURCES' attribute is defined it will be used to calculate resource based costs estimates.
    """

    RESOURCES = []

    @classmethod
    def get_costs_estimates(cls, customer=None):
        """ Get a list of generic/additional estimated costs for the current year/month
            Should return a list of tuples in a form: (entity_obj, monthly_cost)

            Example:

            .. code-block:: python

                for droplet in Droplet.objects.all():
                    yield droplet, droplet.get_cost_estimate()

                yield droplet.service_project_link.service.customer, 0.99
        """
        return
        yield

    @classmethod
    def get_all_costs_estimates(cls, customer=None):
        return itertools.chain(
            cls._get_common_costs_estimates(customer),
            cls._get_resources_costs_estimates(customer))

    @classmethod
    def _get_common_costs_estimates(cls, customer=None):
        estimates = cls.get_costs_estimates(customer)
        if isinstance(estimates, types.GeneratorType):
            return estimates
        else:
            return (e for e in estimates)

    @classmethod
    def _get_resources_costs_estimates(cls, customer=None):
        models = cls.RESOURCES
        if not models:
            return
        if not isinstance(models, (list, tuple)):
            models = [models]

        for model in models:
            queryset = model.objects.exclude(state=model.States.ERRED)
            if customer:
                query = {model.Permissions.customer_path: customer}
                queryset = queryset.filter(**query)

            for instance in queryset.iterator():
                try:
                    backend = instance.get_backend()
                    monthly_cost = backend.get_cost_estimate(instance)
                except ServiceBackendNotImplemented:
                    continue
                except ServiceBackendError as e:
                    logger.error(
                        "Failed to get price estimate for resource %s: %s" % (instance, e))
                else:
                    yield instance, monthly_cost


@lru_cache(maxsize=1)
def get_cost_tracking_models():
    return [m.load() for m in pkg_resources.iter_entry_points('cost_tracking_strategies')]
