import datetime
import logging

from dateutil.relativedelta import relativedelta
from django.utils import timezone

from nodeconductor.core import utils as core_utils
from nodeconductor.cost_tracking import exceptions, models, CostTrackingRegister, ResourceNotRegisteredError
from nodeconductor.structure import ServiceBackendNotImplemented, ServiceBackendError, models as structure_models


logger = logging.getLogger(__name__)


# XXX: Should we copy limit too?
def copy_threshold_from_previous_price_estimate(sender, instance, created=False, **kwargs):
    if created and instance.scope:
        current_date = datetime.date.today().replace(year=instance.year, month=instance.month, day=1)
        prev_date = current_date - relativedelta(months=1)
        try:
            prev_estimate = models.PriceEstimate.objects.get(
                year=prev_date.year,
                month=prev_date.month,
                scope=instance.scope,
                threshold__gt=0
            )
            instance.threshold = prev_estimate.threshold
            instance.save(update_fields=['threshold'])
        except models.PriceEstimate.DoesNotExist:
            pass


# XXX: Why is this only for project, but not for customer?
#      Looks strange that we are checking project separately.
#      I think this error should be raised for each price estimate independently
#      from object. NC-1537
def check_project_cost_limit_on_resource_provision(sender, instance, **kwargs):
    resource = instance

    try:
        project = resource.service_project_link.project
        estimate = models.PriceEstimate.objects.get_current(project)
    except models.PriceEstimate.DoesNotExist:
        return

    # Project cost is unlimited
    if estimate.limit == -1:
        return

    # Early check
    if estimate.total > estimate.limit:
        raise exceptions.CostLimitExceeded(
            detail='Estimated cost of project is over limit.')

    try:
        cost_tracking_backend = CostTrackingRegister.get_resource_backend(resource)
        monthly_cost = float(cost_tracking_backend.get_monthly_cost_estimate(resource))
    except ServiceBackendNotImplemented:
        return
    except ServiceBackendError as e:
        logger.error("Failed to get cost estimate for resource %s: %s", resource, e)
        return
    except Exception as e:
        logger.exception("Failed to get cost estimate for resource %s: %s", resource, e)
        return

    if estimate.total + monthly_cost > estimate.limit:
        raise exceptions.CostLimitExceeded(
            detail='Total estimated cost of resource and project is over limit.')


def scope_deletion(sender, instance, **kwargs):
    """ Run different actions on price estimate scope deletion.

        If scope is a customer - delete all customer estimates and their children.
        If scope is a deleted resource - redefine consumption details, recalculate
                                         ancestors estimates and update estimate details.
        If scope is a unlinked resource - delete all resource price estimates and update ancestors.
        In all other cases - update price estimate details.
    """

    is_resource = isinstance(instance, structure_models.ResourceMixin)
    if is_resource and getattr(instance, 'PERFORM_UNLINK', False):
        _resource_unlink(resource=instance)
    elif is_resource and not getattr(instance, 'PERFORM_UNLINK', False):
        _resource_deletion(resource=instance)
    elif isinstance(instance, structure_models.Customer):
        _customer_deletion(customer=instance)
    else:
        for price_estimate in models.PriceEstimate.objects.filter(scope=instance):
            price_estimate.init_details()


def _resource_unlink(resource):
    if resource.__class__ not in CostTrackingRegister.registered_resources:
        return
    for price_estimate in models.PriceEstimate.objects.filter(scope=resource):
        price_estimate.update_ancestors_total(diff=-price_estimate.total)
        price_estimate.delete()


def _customer_deletion(customer):
    for estimate in models.PriceEstimate.objects.filter(scope=customer):
        for descendant in estimate.get_descendants():
            descendant.delete()


def _resource_deletion(resource):
    """ Recalculate consumption details and save resource details """
    if resource.__class__ not in CostTrackingRegister.registered_resources:
        return
    new_configuration = {}
    price_estimate = _update_resource_estimate(resource, new_configuration)
    price_estimate.init_details()


def resource_update(sender, instance, created=False, **kwargs):
    """ Update resource consumption details and price estimate if its configuration has changed.
        Create estimates for previous months if resource was created not in current month.
    """
    resource = instance
    try:
        new_configuration = CostTrackingRegister.get_configuration(resource)
    except ResourceNotRegisteredError:
        return
    _update_resource_estimate(resource, new_configuration)
    # Try to create historical price estimates
    if created:
        _create_historical_estimates(resource, new_configuration)


def resource_quota_update(sender, instance, **kwargs):
    """ Update resource consumption details and price estimate if its configuration has changed """
    quota = instance
    resource = quota.scope
    try:
        new_configuration = CostTrackingRegister.get_configuration(resource)
    except ResourceNotRegisteredError:
        return
    _update_resource_estimate(resource, new_configuration)


def _create_historical_estimates(resource, configuration):
    """ Create consumption details and price estimates for past months.

        Usually we need to update historical values on resource import.
    """
    today = timezone.now()
    month_start = core_utils.month_start(today)
    while month_start > resource.created:
        month_start -= relativedelta(months=1)
        models.PriceEstimate.create_historical(resource, configuration, max(month_start, resource.created))


def _update_resource_estimate(resource, new_configuration):
    price_estimate, created = models.PriceEstimate.objects.get_or_create_current(scope=resource)
    if created:
        price_estimate.create_ancestors()
    consumption_details, _ = models.ConsumptionDetails.objects.get_or_create(price_estimate=price_estimate)
    consumption_details.update_configuration(new_configuration)
    price_estimate.update_total()
    return price_estimate
