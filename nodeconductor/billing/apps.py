from __future__ import unicode_literals

from django.apps import AppConfig
from django.db.models import signals

from nodeconductor.billing import handlers


class BillingConfig(AppConfig):
    name = 'nodeconductor.billing'
    verbose_name = 'NodeConductor Billing'

    def ready(self):
        Invoice = self.get_model('Invoice')

        signals.post_save.connect(
            handlers.log_invoice_save,
            sender=Invoice,
            dispatch_uid='nodeconductor.structure.handlers.log_invoice_save',
        )

        signals.post_delete.connect(
            handlers.log_invoice_delete,
            sender=Invoice,
            dispatch_uid='nodeconductor.structure.handlers.log_invoice_delete',
        )
