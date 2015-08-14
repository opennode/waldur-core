from __future__ import unicode_literals

from django.apps import AppConfig
from django.db.models import signals
from django_fsm.signals import post_transition
from django.conf import settings

from nodeconductor.billing import handlers
from nodeconductor.billing.models import PaidResource
from nodeconductor.structure import models as structure_models


class BillingConfig(AppConfig):
    name = 'nodeconductor.billing'
    verbose_name = 'NodeConductor Billing'

    def ready(self):
        Invoice = self.get_model('Invoice')

        signals.post_save.connect(
            handlers.log_invoice_save,
            sender=Invoice,
            dispatch_uid='nodeconductor.billing.handlers.log_invoice_save',
        )

        signals.post_delete.connect(
            handlers.log_invoice_delete,
            sender=Invoice,
            dispatch_uid='nodeconductor.billing.handlers.log_invoice_delete',
        )

        nc_settings = getattr(settings, 'NODECONDUCTOR', {})
        if nc_settings.get('ENABLE_WHMCS_ORDER_PROCESSING', False):
            for index, resource in enumerate(structure_models.Resource.get_all_models()):
                if issubclass(resource, PaidResource):
                    signals.post_delete.connect(
                        handlers.terminate_purchase,
                        sender=resource,
                        dispatch_uid='nodeconductor.billing.handlers.terminate_purchase_{}_{}'.format(
                            resource.__name__, index),
                    )

                    post_transition.connect(
                        handlers.track_order,
                        sender=resource,
                        dispatch_uid='nodeconductor.billing.handlers.track_order_{}_{}'.format(
                            resource.__name__, index),
                    )
