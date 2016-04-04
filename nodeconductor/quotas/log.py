from nodeconductor.logging.loggers import AlertLogger, EventLogger, alert_logger, event_logger
from nodeconductor.quotas import models


class QuotaAlertLogger(AlertLogger):
    quota = models.Quota

    class Meta:
        alert_types = ('quota_usage_is_over_threshold',)


class QuotaEventLogger(EventLogger):
    quota = 'quotas.Quota'
    service = 'structure.Service'
    project = 'structure.Project'
    project_group = 'structure.ProjectGroup'
    threshold = float

    class Meta:
        event_types = ('quota_threshold_reached',)


alert_logger.register('quota', QuotaAlertLogger)
event_logger.register('quota', QuotaEventLogger)
