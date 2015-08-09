from __future__ import unicode_literals

from django.apps import AppConfig
from django.db.models import signals
from django_fsm.signals import post_transition

from nodeconductor.billing import handlers
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

        for index, resource in enumerate(structure_models.Resource.get_all_models()):
            signals.post_delete.connect(
                handlers.cancel_purchase,
                sender=resource,
                dispatch_uid='nodeconductor.billing.handlers.cancel_purchase_{}_{}'.format(
                    resource.__name__, index),
            )

            post_transition.connect(
                handlers.track_order,
                sender=resource,
                dispatch_uid='nodeconductor.billing.handlers.track_order_{}_{}'.format(
                    resource.__name__, index),
            )
