import logging

from django.contrib.contenttypes.models import ContentType

from nodeconductor.core.tasks import send_task
from nodeconductor.cost_tracking import models
from nodeconductor.structure.models import Resource
from nodeconductor.structure import SupportedServices


logger = logging.getLogger('nodeconductor.cost_tracking')


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


def create_price_list_items_for_service(sender, instance, created=False, **kwargs):
    if created:
        service = instance
        resource_content_type = ContentType.objects.get_for_model(service)
        for default_item in models.DefaultPriceListItem.objects.filter(resource_content_type=resource_content_type):
            models.PriceListItem.objects.create(
                resource_content_type=resource_content_type,
                service=service,
                key=default_item.key,
                item_type=default_item.item_type,
                value=default_item.value,
                units=default_item.units,
            )


def change_price_list_items_if_default_was_changed(sender, instance, created=False, **kwargs):
    default_item = instance
    if created:
        # if new default item added - we create such item in for each service
        model = default_item.resource_content_type.model_class()
        service_class = SupportedServices.get_related_models(model)['service']
        for service in service_class.objects.all():
            models.PriceListItem.objects.create(
                resource_content_type=default_item.resource_content_type,
                service=service,
                key=default_item.key,
                item_type=default_item.item_type,
                units=default_item.units,
                value=default_item.value
            )
    else:
        if default_item.tracker.has_changed('key') or default_item.tracker.has_changed('item_type'):
            # if default item key or item type was changed - it will be changed in each connected item
            connected_items = models.PriceListItem.objects.filter(
                key=default_item.tracker.previous('key'),
                item_type=default_item.tracker.previous('item_type'),
                resource_content_type=default_item.resource_content_type,
            )
        else:
            # if default value or units changed - it will be changed in each connected item
            # that was not edited manually
            connected_items = models.PriceListItem.objects.filter(
                key=default_item.key,
                item_type=default_item.item_type,
                resource_content_type=default_item.resource_content_type,
                is_manually_input=False,
            )
        connected_items.update(
            key=default_item.key, item_type=default_item.item_type, units=default_item.units, value=default_item.value)


def delete_price_list_items_if_default_was_deleted(sender, instance, **kwargs):
    default_item = instance
    models.PriceListItem.objects.filter(
        key=default_item.tracker.previous('key'),
        item_type=default_item.tracker.previous('item_type'),
        resource_content_type=default_item.resource_content_type,
    ).delete()


def update_price_estimate_on_resource_import(sender, instance, **kwargs):
    send_task('cost_tracking', 'update_projected_estimate')(
        resource_str=instance.to_string())


def add_resource_price_estimate_on_provision(sender, instance, name=None, source=None, **kwargs):
    if source == instance.States.PROVISIONING and name == instance.set_online.__name__:
        update_price_estimate_on_resource_import(sender, instance)


def update_price_estimate_ancestors(sender, instance, created=False, **kwargs):
    # ignore created -- avoid double call from PriceEstimate.update_price_for_resource.update_estimate
    if not created and instance.is_leaf:
        instance.update_ancestors()


def update_price_estimate_on_resource_spl_change(sender, instance, created=False, **kwargs):
    try:
        # XXX: drop support of IaaS app
        is_changed = not created and instance.service_project_link_id != instance._old_values['service_project_link']
    except AttributeError:
        is_changed = False

    if is_changed:
        spl_model = SupportedServices.get_related_models(instance)['service_project_link']
        spl_old = spl_model.objects.get(pk=instance._old_values['service_project_link'])

        old_family_scope = [spl_old] + spl_old.get_ancestors()
        for estimate in models.PriceEstimate.filter(scope=instance, is_manually_input=False):
            qs = models.PriceEstimate.objects.filter(
                scope__in=old_family_scope, month=estimate.month, year=estimate.year)
            for parent_estimate in qs:
                parent_estimate.leaf_estimates.remove(estimate)
                parent_estimate.update_from_leaf()

        models.PriceEstimate.update_ancestors_for_resource(instance, force=True)


def delete_price_estimate_on_scope_deletion(sender, instance, **kwargs):
    # if scope is Resource:
    #    delete -- add metadata about deleted resource, set object_id to NULL
    #    unlink -- delete all related estimates
    if isinstance(instance, tuple(Resource.get_all_models())):
        if getattr(instance, 'PERFORM_UNLINK', False):
            models.PriceEstimate.delete_estimates_for_resource(instance)
        else:
            models.PriceEstimate.update_metadata_for_scope(instance)
            # deal with re-usage of primary keys in InnoDB
            models.PriceEstimate.objects.filter(scope=instance).update(object_id=None)

    # otherwise delete everything in hope of django carrying out DB consistency
    # i.e. higher level scope can only be deleted if there's no any resource in it
    else:
        models.PriceEstimate.objects.filter(scope=instance).delete()
