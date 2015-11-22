from __future__ import unicode_literals

from django.apps import AppConfig
from django.db.models import signals

from nodeconductor.template import handlers, get_template_services


class TemplateConfig(AppConfig):
    name = 'nodeconductor.template'
    verbose_name = 'NodeConductor Template'

    def ready(self):
        Template = self.get_model('Template')

        signals.post_save.connect(
            handlers.log_template_save,
            sender=Template,
            dispatch_uid='nodeconductor.template.handlers.log_template_save',
        )

        signals.post_delete.connect(
            handlers.log_template_delete,
            sender=Template,
            dispatch_uid='nodeconductor.template.handlers.log_template_delete',
        )

        for service in get_template_services():
            service_type = service.service_type.lower()
            signals.post_save.connect(
                handlers.log_template_service_save,
                sender=service,
                dispatch_uid='nodeconductor.template.handlers.log_template_service_%s_save' % service_type,
            )

            signals.post_delete.connect(
                handlers.log_template_service_delete,
                sender=service,
                dispatch_uid='nodeconductor.template.handlers.log_template_service_%s_delete' % service_type,
            )
