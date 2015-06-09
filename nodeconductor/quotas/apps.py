from __future__ import unicode_literals

from django.apps import AppConfig
from django.db.models import signals

from nodeconductor.quotas import handlers


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

        signals.post_save.connect(
            handlers.create_quota_log,
            sender=Quota
        )
