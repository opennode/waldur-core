from __future__ import unicode_literals

from django.apps import AppConfig
from django.db.models import signals
from django_fsm.signals import post_transition


class CostTrackingConfig(AppConfig):
    name = 'nodeconductor.cost_tracking'
    verbose_name = 'Cost tracking'

    def ready(self):
        from nodeconductor.core.handlers import preserve_fields_before_update
        from nodeconductor.cost_tracking import handlers
        from nodeconductor.structure import models as structure_models
        from nodeconductor.structure.signals import resource_imported, resource_provisioned

        PriceEstimate = self.get_model('PriceEstimate')

        signals.post_save.connect(
            handlers.make_autocalculate_price_estimate_invisible_on_manual_estimate_creation,
            sender=PriceEstimate,
            dispatch_uid=('nodeconductor.cost_tracking.handlers.'
                          'make_autocalculate_price_estimate_invisible_on_manual_estimate_creation')
        )

        signals.post_delete.connect(
            handlers.make_autocalculated_price_estimate_visible_on_manual_estimate_deletion,
            sender=PriceEstimate,
            dispatch_uid=('nodeconductor.cost_tracking.handlers.'
                          'make_autocalculated_price_estimate_visible_on_manual_estimate_deletion')
        )

        signals.post_save.connect(
            handlers.make_autocalculate_price_estimate_invisible_if_manually_created_estimate_exists,
            sender=PriceEstimate,
            dispatch_uid=('nodeconductor.cost_tracking.handlers.'
                          'make_autocalculate_price_estimate_invisible_if_manually_created_estimate_exists')
        )

        signals.post_save.connect(
            handlers.copy_threshold_from_previous_price_estimate,
            sender=PriceEstimate,
            dispatch_uid='nodeconductor.cost_tracking.handlers.copy_threshold_from_previous_price_estimate'
        )

        signals.post_save.connect(
            handlers.update_price_estimate_ancestors,
            sender=PriceEstimate,
            dispatch_uid='nodeconductor.cost_tracking.handlers.update_price_estimate_ancestors'
        )

        for index, resource in enumerate(structure_models.ResourceMixin.get_all_models()):
            signals.pre_save.connect(
                preserve_fields_before_update,
                sender=resource,
                dispatch_uid=(
                    'nodeconductor.cost_tracking.handlers.preserve_fields_before_update_{}_{}'
                    .format(resource.__name__, index))
            )

            signals.pre_save.connect(
                handlers.check_project_cost_limit_on_resource_provision,
                sender=resource,
                dispatch_uid=(
                    'nodeconductor.cost_tracking.handlers.check_project_cost_limit_on_resource_provision_{}_{}'
                    .format(resource.__name__, index))
            )

            signals.post_save.connect(
                handlers.update_price_estimate_on_resource_spl_change,
                sender=resource,
                dispatch_uid=(
                    'nodeconductor.cost_tracking.handlers.update_price_estimate_on_resource_spl_change_{}_{}'
                    .format(resource.__name__, index))
            )

            resource_imported.connect(
                handlers.update_projected_estimate,
                sender=resource,
                dispatch_uid=(
                    'nodeconductor.cost_tracking.handlers.update_price_estimate_on_resource_import_{}_{}'
                    .format(resource.__name__, index))
            )

            resource_provisioned.connect(
                handlers.update_projected_estimate,
                sender=resource,
                dispatch_uid=(
                    'nodeconductor.cost_tracking.handlers.add_resource_price_estimate_on_provision_{}_{}'
                    .format(resource.__name__, index))
            )

        for index, model in enumerate(PriceEstimate.get_estimated_models()):
            signals.pre_delete.connect(
                handlers.delete_price_estimate_on_scope_deletion,
                sender=model,
                dispatch_uid=('nodeconductor.cost_tracking.handlers.delete_price_estimate_on_scope_deletion_{}_{}'
                              .format(model.__name__, index))
            )
