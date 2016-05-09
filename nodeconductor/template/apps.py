from django.apps import AppConfig
from django.conf import settings
from django_fsm import signals as fsm_signals


class TemplateConfig(AppConfig):
    name = 'nodeconductor.template'
    verbose_name = 'Template'
    is_itacloud = getattr(settings, 'NODECONDUCTOR', {}).get('IS_ITACLOUD', False)

    def ready(self):
        if self.is_itacloud:
            # TODO: this should be moved to GCloud assembly application
            from nodeconductor.openstack.models import Instance
            from nodeconductor.template import handlers

            fsm_signals.post_transition.connect(
                handlers.create_host_for_instance,
                sender=Instance,
                dispatch_uid='nodeconductor.template.handlers.create_host_for_instance',
            )
