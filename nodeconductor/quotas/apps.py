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
            handlers.check_if_quota_is_over_threshold,
            sender=Quota,
            dispatch_uid='nodeconductor.quotas.handlers.check_alert_if_quota_is_over_threshold',
        )
