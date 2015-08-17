from __future__ import unicode_literals

from django.apps import AppConfig
from django.db.models import signals

from nodeconductor.quotas import handlers, utils


class QuotasConfig(AppConfig):
    name = 'nodeconductor.quotas'
    verbose_name = "NodeConductor Quotas"

    def ready(self):
        Quota = self.get_model('Quota')

        signals.post_save.connect(
            handlers.check_quota_threshold_breach,
            sender=Quota,
            dispatch_uid='nodeconductor.quotas.handlers.check_quota_threshold_breach',
        )

        for index, model in enumerate(utils.get_models_with_quotas()):
            signals.pre_delete.connect(
                handlers.reset_quota_values_to_zeros_before_delete,
                sender=model,
                dispatch_uid=('nodeconductor.quotas.handlers.reset_quota_values_to_zeros_before_delete_%s_%s'
                              % (model.__name__, index)),
            )
