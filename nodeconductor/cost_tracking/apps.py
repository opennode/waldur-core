from __future__ import unicode_literals

from django.apps import AppConfig
from django.db.models import signals


class CostTrackingConfig(AppConfig):
    name = 'nodeconductor.cost_tracking'
    verbose_name = 'Cost tracking'

    def ready(self):
        from nodeconductor.cost_tracking import handlers
        from nodeconductor.quotas import models as quotas_models
        from nodeconductor.structure import models as structure_models

        PriceEstimate = self.get_model('PriceEstimate')

        for index, model in enumerate(PriceEstimate.get_estimated_models()):
            signals.pre_delete.connect(
                handlers.scope_deletion,
                sender=model,
                dispatch_uid='nodeconductor.cost_tracking.handlers.scope_deletion_%s_%s' % (model.__name__, index),
            )

        for index, model in enumerate(structure_models.ResourceMixin.get_all_models()):
            signals.post_save.connect(
                handlers.resource_update,
                sender=model,
                dispatch_uid='nodeconductor.cost_tracking.resource_update_%s_%s' % (model.__name__, index),
            )

        signals.post_save.connect(
            handlers.resource_quota_update,
            sender=quotas_models.Quota,
            dispatch_uid='nodeconductor.cost_tracking.handlers.resource_quota_update',
        )

        signals.post_save.connect(
            handlers.copy_threshold_from_previous_price_estimate,
            sender=PriceEstimate,
            dispatch_uid='nodeconductor.cost_tracking.handlers.copy_threshold_from_previous_price_estimate'
        )
