from nodeconductor.logging.log import EventLogger, event_logger
from nodeconductor.template.models import Template, TemplateService


class TemplateEventLogger(EventLogger):
    template = Template

    class Meta:
        event_types = ('template_creation_succeeded',
                       'template_update_succeeded',
                       'template_deletion_succeeded')


class TemplateServiceEventLogger(EventLogger):
    template_service = TemplateService

    class Meta:
        event_types = ('template_service_creation_succeeded',
                       'template_service_update_succeeded',
                       'template_service_deletion_succeeded')


event_logger.register('template', TemplateEventLogger)
event_logger.register('template_service', TemplateServiceEventLogger)
