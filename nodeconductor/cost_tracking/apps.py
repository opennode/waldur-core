from __future__ import unicode_literals

from django.apps import AppConfig
from django.db.models import signals

from nodeconductor.cost_tracking import handlers


class CostTrackingConfig(AppConfig):
    name = 'nodeconductor.cost_tracking'
    verbose_name = "NodeConductor Cost Tracking"

    def ready(self):
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

        signals.pre_save.connect(
            handlers.make_autocalculate_price_estimate_invisible_if_manually_created_estimate_exists,
            sender=PriceEstimate,
            dispatch_uid=('nodeconductor.cost_tracking.handlers.'
                          'make_autocalculate_price_estimate_invisible_if_manually_created_estimate_exists')
        )
