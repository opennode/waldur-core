from django.apps import AppConfig


class TemplateConfig(AppConfig):
    name = 'nodeconductor.template'
    verbose_name = "NodeConductor Template"

    def ready(self):
        pass
