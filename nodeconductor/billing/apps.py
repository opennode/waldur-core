from __future__ import unicode_literals

from django.apps import AppConfig
from django.db.models import signals
from django_fsm.signals import post_transition
from django.conf import settings

from nodeconductor.billing import handlers, get_paid_resource_models
from nodeconductor.structure import models as structure_models
from nodeconductor.core.handlers import preserve_fields_before_update


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
        if nc_settings.get('ENABLE_ORDER_PROCESSING', False):
            for index, resource in enumerate(get_paid_resource_models()):
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

                signals.pre_save.connect(
                    preserve_fields_before_update,
                    sender=resource,
                    dispatch_uid='nodeconductor.billing.handlers.preserve_fields_before_update_{}_{}'.format(
                        resource.__name__, index),
                )

                signals.post_save.connect(
                    handlers.update_resource_name,
                    sender=resource,
                    dispatch_uid='nodeconductor.billing.handlers.update_resource_name_{}_{}'.format(
                        resource.__name__, index),
                )

            signals.post_save.connect(
                handlers.update_project_name,
                sender=structure_models.Project,
                dispatch_uid='nodeconductor.billing.handlers.update_project_name',
            )

            signals.post_save.connect(
                handlers.update_project_group_name,
                sender=structure_models.ProjectGroup,
                dispatch_uid='nodeconductor.billing.handlers.update_project_group_name',
            )
