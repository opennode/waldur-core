import logging

from nodeconductor.billing.log import event_logger
from nodeconductor.billing.models import PaidResource


logger = logging.getLogger('nodeconductor.billing')


def log_invoice_save(sender, instance, created=False, **kwargs):
    if created:
        event_logger.invoice.info(
            '{invoice_date}. Invoice for customer {customer_name} has been created.',
            event_type='invoice_creation_succeeded',
            event_context={
                'invoice': instance,
            })
    else:
        event_logger.invoice.info(
            '{invoice_date}. Invoice for customer {customer_name} has been updated.',
            event_type='invoice_update_succeeded',
            event_context={
                'invoice': instance,
            })


def log_invoice_delete(sender, instance, **kwargs):
    event_logger.invoice.info(
        '{invoice_date}. Invoice for customer {customer_name} has been deleted.',
        event_type='invoice_deletion_succeeded',
        event_context={
            'invoice': instance,
        })


def track_order(sender, instance, name=None, source=None, **kwargs):
    if source == instance.States.PROVISIONING and name == instance.set_online.__name__:
        instance.order.subscribe()


def terminate_purchase(sender, instance=None, **kwargs):
    instance.order.terminate()


def update_resource_name(sender, instance, created=False, **kwargs):
    if not created and instance.billing_backend_id and instance.name != instance._old_values['name']:
        instance.order.backend.update_subscription_fields(
            instance.billing_backend_id,
            resource_name=instance.name)


def update_project_name(sender, instance, created=False, **kwargs):
    if not created and instance.tracker.has_changed('name'):
        for model in PaidResource.get_all_models():
            for resource in model.objects.filter(project=instance):
                resource.order.backend.update_subscription_fields(
                    resource.billing_backend_id,
                    project_name=resource.project.full_name)


def update_project_group_name(sender, instance, created=False, **kwargs):
    if not created and instance.tracker.has_changed('name'):
        for model in PaidResource.get_all_models():
            for resource in model.objects.filter(project__project_groups=instance):
                resource.order.backend.update_subscription_fields(
                    resource.billing_backend_id,
                    project_name=resource.project.full_name)
