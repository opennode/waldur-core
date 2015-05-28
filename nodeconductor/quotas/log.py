from nodeconductor.events.log import AlertLogger, alert_logger
from nodeconductor.quotas import models


class QuotaAlertLogger(AlertLogger):
    quota = models.Quota

    class Meta:
        alert_types = ('quota_usage_is_over_threshold', )


alert_logger.register('quota', QuotaAlertLogger)
