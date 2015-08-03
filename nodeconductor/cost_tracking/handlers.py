from django.contrib.contenttypes.models import ContentType

from nodeconductor.cost_tracking import models


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
        service_content_type = ContentType.objects.get_for_model(service)
        for key, item_type in models.PriceKeysRegister.get_keys_with_types_for_service(service):
            default_item = models.DefaultPriceListItem.objects.get(
                key=key, item_type=item_type, service_content_type=service_content_type)
            models.PriceListItem.objects.create(
                service=service,
                key=key,
                item_type=item_type,
                value=default_item.value,
                units=default_item.units,
            )


def create_resource_price_items_for_resource(sender, instance, created=False, **kwargs):
    if created:
        resource = instance
        service = resource.service_project_link.service
        for key, item_type in models.PriceKeysRegister.get_keys_with_types_for_resource(resource):
            price_list_item = models.PriceListItem.objects.get(key=key, item_type=item_type, service=service)
            models.ResourcePriceItem.objects.create(item=price_list_item, resource=resource)


def create_default_price_list_items(**kwargs):
    for service in models.PriceKeysRegister.services:
        service_content_type = ContentType.objects.get_for_model(service)
        for key, item_type in models.PriceKeysRegister.get_keys_with_types_for_service(service):
            models.DefaultPriceListItem.objects.get_or_create(
                key=key,
                item_type=item_type,
                service_content_type=service_content_type,
            )
