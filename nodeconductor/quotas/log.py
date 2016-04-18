from nodeconductor.logging.loggers import AlertLogger, EventLogger, alert_logger, event_logger
from nodeconductor.quotas import models


# Remove once IAAS is deprecated
class QuotaEventLogger(EventLogger):
    quota = 'quotas.Quota'
    service = 'structure.Service'
    project = 'structure.Project'
    project_group = 'structure.ProjectGroup'
    threshold = float

    class Meta:
        event_types = ('quota_threshold_reached',)


event_logger.register('quota', QuotaEventLogger)
