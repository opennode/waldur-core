from __future__ import unicode_literals

import datetime
import logging

from celery import current_task
from dateutil.relativedelta import relativedelta
from django.utils import timezone

from nodeconductor.core import utils as core_utils
from nodeconductor.cost_tracking import models, CostTrackingRegister, ResourceNotRegisteredError
from nodeconductor.structure import models as structure_models

from . import log


logger = logging.getLogger(__name__)


def copy_from_previous_price_estimate(sender, instance, created=False, **kwargs):
    """ Copy limit and threshold from previous price estimate """
    if created and instance.scope:
        current_date = datetime.date.today().replace(year=instance.year, month=instance.month, day=1)
        prev_date = current_date - relativedelta(months=1)
        try:
            prev_estimate = models.PriceEstimate.objects.get(
                year=prev_date.year,
                month=prev_date.month,
                scope=instance.scope,
            )
        except models.PriceEstimate.DoesNotExist:
            pass
        else:
            instance.threshold = prev_estimate.threshold
            instance.limit = prev_estimate.limit
            instance.save(update_fields=['threshold', 'limit'])


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
    price_estimate = models.PriceEstimate.update_resource_estimate(resource, new_configuration)
    price_estimate.init_details()


def _is_in_celery_task():
    """ Return True if current code is executed in celery task """
    return bool(current_task)


def resource_update(sender, instance, created=False, **kwargs):
    """ Update resource consumption details and price estimate if its configuration has changed.
        Create estimates for previous months if resource was created not in current month.
    """
    resource = instance
    try:
        new_configuration = CostTrackingRegister.get_configuration(resource)
    except ResourceNotRegisteredError:
        return
    models.PriceEstimate.update_resource_estimate(
        resource, new_configuration, raise_exception=not _is_in_celery_task())
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
    models.PriceEstimate.update_resource_estimate(
        resource, new_configuration, raise_exception=not _is_in_celery_task())


def _create_historical_estimates(resource, configuration):
    """ Create consumption details and price estimates for past months.

        Usually we need to update historical values on resource import.
    """
    today = timezone.now()
    month_start = core_utils.month_start(today)
    while month_start > resource.created:
        month_start -= relativedelta(months=1)
        models.PriceEstimate.create_historical(resource, configuration, max(month_start, resource.created))


def log_price_estimate_limit_update(sender, instance, created=False, **kwargs):
    if created:
        return

    if instance.tracker.has_changed('limit'):
        if isinstance(instance.scope, structure_models.Customer):
            event_type = 'project_price_limit_updated'
        elif isinstance(instance.scope, structure_models.Project):
            event_type = 'customer_price_limit_updated'
        else:
            logger.warning('A price estimate event for type of "%s" is not registered.', type(instance.scope))
            return

        message = 'Price limit for "%(scope)s" has been updated from "%(old)s" to "%(new)s".' % {
            'scope': instance.scope,
            'old': instance.tracker.previous('limit'),
            'new': instance.limit
        }
        log.event_logger.price_estimate.info(message, event_type=event_type)
