import datetime
import logging

from dateutil.relativedelta import relativedelta

from nodeconductor.core.tasks import send_task
from nodeconductor.core.utils import serialize_instance
from nodeconductor.cost_tracking import exceptions, models, CostTrackingRegister
from nodeconductor.cost_tracking.models import PayableMixin
from nodeconductor.structure import SupportedServices, ServiceBackendNotImplemented, ServiceBackendError
from nodeconductor.structure import models as structure_models


logger = logging.getLogger(__name__)


def make_autocalculate_price_estimate_invisible_on_manual_estimate_creation(sender, instance, created=False, **kwargs):
    if created and instance.is_manually_input:
        manually_created_price_estimate = instance
        (models.PriceEstimate.objects
            .filter(scope=manually_created_price_estimate.scope,
                    year=manually_created_price_estimate.year,
                    month=manually_created_price_estimate.month,
                    is_manually_input=False)
            .update(is_visible=False))


def make_autocalculated_price_estimate_visible_on_manual_estimate_deletion(sender, instance, **kwargs):
    deleted_price_estimate = instance
    if deleted_price_estimate.is_manually_input:
        (models.PriceEstimate.objects
            .filter(scope=deleted_price_estimate.scope,
                    year=deleted_price_estimate.year,
                    month=deleted_price_estimate.month,
                    is_manually_input=False)
            .update(is_visible=True))


def make_autocalculate_price_estimate_invisible_if_manually_created_estimate_exists(
        sender, instance, created=False, **kwargs):
    if created and not instance.is_manually_input:
        if models.PriceEstimate.objects.filter(
                year=instance.year, scope=instance.scope, month=instance.month, is_manually_input=True).exists():
            instance.is_visible = False


def copy_threshold_from_previous_price_estimate(sender, instance, created=False, **kwargs):
    if created:
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


def update_projected_estimate(sender, instance, back_propagate_price=False, **kwargs):
    send_task('cost_tracking', 'update_projected_estimate')(
        serialized_resource=serialize_instance(instance),
        back_propagate_price=back_propagate_price
    )


def update_price_estimate_ancestors(sender, instance, created=False, **kwargs):
    # ignore created -- avoid double call from PriceEstimate.update_price_for_resource.update_estimate
    if not created and instance.is_leaf:
        instance.update_ancestors()


def update_price_estimate_on_resource_spl_change(sender, instance, created=False, **kwargs):
    is_changed = not created and instance.service_project_link_id != instance._old_values['service_project_link']

    if is_changed:
        spl_model = SupportedServices.get_related_models(instance)['service_project_link']
        spl_old = spl_model.objects.get(pk=instance._old_values['service_project_link'])

        old_family_scope = [spl_old] + spl_old.get_ancestors()
        for estimate in models.PriceEstimate.objects.filter(scope=instance, is_manually_input=False):
            qs = models.PriceEstimate.objects.filter(
                scope__in=old_family_scope, month=estimate.month, year=estimate.year)
            for parent_estimate in qs:
                parent_estimate.leaf_estimates.remove(estimate)
                parent_estimate.update_from_leaf()

        models.PriceEstimate.update_ancestors_for_resource(instance)


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


def delete_price_estimate_on_scope_deletion(sender, instance, **kwargs):
    # If scope is resource:
    #    delete -- add metadata about deleted resource, set object_id to NULL
    #    unlink -- delete all related estimates
    if isinstance(instance, PayableMixin):
        if getattr(instance, 'PERFORM_UNLINK', False):
            models.PriceEstimate.delete_estimates_for_resource(instance)
        else:
            models.PriceEstimate.update_metadata_for_resource(instance)
            # deal with re-usage of primary keys in InnoDB
            models.PriceEstimate.objects.filter(scope=instance).update(object_id=None)

    # If scope is customer or service project link then delete all related estimates
    elif isinstance(instance, (structure_models.Customer,
                               structure_models.ServiceProjectLink)):
        models.PriceEstimate.objects.filter(scope=instance).delete()

    # Else add metadata about deleted object, set object_id to NULL
    elif isinstance(instance, (structure_models.Service,
                               structure_models.ServiceSettings,
                               structure_models.Project)):
        models.PriceEstimate.update_metadata_for_scope(instance)
        models.PriceEstimate.objects.filter(scope=instance).update(object_id=None)
