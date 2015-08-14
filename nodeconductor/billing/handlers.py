import logging

from nodeconductor.billing.log import event_logger
from nodeconductor.billing.backend import BillingBackendError
from nodeconductor.cost_tracking import models


logger = logging.getLogger('nodeconductor.billing')


def log_invoice_save(sender, instance, created=False, **kwargs):
    if created:
        event_logger.invoice.info(
            'Invoice for customer {customer_name} for the period of {invoice_date} has been created.',
            event_type='invoice_creation_succeeded',
            event_context={
                'invoice': instance,
            })
    else:
        event_logger.invoice.info(
            'Invoice for customer {customer_name} for the period of {invoice_date} has been updated.',
            event_type='invoice_update_succeeded',
            event_context={
                'invoice': instance,
            })


def log_invoice_delete(sender, instance, **kwargs):
    event_logger.invoice.info(
        'Invoice for customer {customer_name} for the period of {invoice_date} has been deleted.',
        event_type='invoice_deletion_succeeded',
        event_context={
            'invoice': instance,
        })


def track_order(sender, instance, name=None, source=None, **kwargs):
    if not issubclass(instance.__class__, models.PaidResource):
        return

    order = instance.order
    try:
        if name == instance.begin_provisioning.__name__:
            order.setup()

        if name == instance.set_online.__name__:
            if source == instance.States.PROVISIONING:
                order.confirm()
            if source == instance.States.STARTING:
                order.update(flavor=instance.flavor_name)

        if name == instance.set_offline.__name__:
            if source == instance.States.STOPPING:
                order.update(flavor=None)

        if name == instance.set_erred.__name__:
            if source == instance.States.PROVISIONING:
                order.cancel()

        if name == instance.set_resized.__name__:
            order.update(flavor=None)

    except BillingBackendError:
        logger.exception("Failed to track order for resource %s" % instance)
        instance.state = instance.States.ERRED
        instance.save()


def terminate_purchase(sender, instance=None, **kwargs):
    if issubclass(instance.__class__, models.PaidResource):
        instance.order.terminate()
