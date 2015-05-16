
import pkg_resources

from django.utils.lru_cache import lru_cache


default_app_config = 'nodeconductor.template.apps.TemplateConfig'


class TemplateProvisionError(Exception):
    def __init__(self, errors=()):
        self.errors = errors


class TemplateServiceStrategy(object):
    """ A parent class for the model-specific template strategies. """

    @classmethod
    def get_model(cls):
        raise NotImplementedError(
            'Implement get_model() that would return TemplateService inherited model.')

    @classmethod
    def get_serializer(cls):
        raise NotImplementedError(
            'Implement get_serializer() that would return TemplateService model serializer.')

    @classmethod
    def get_admin_form(cls):
        pass


@lru_cache(maxsize=1)
def get_template_services():
    services = []
    entry_points = pkg_resources.get_entry_map('nodeconductor').get('template_services', {})
    for name, entry_point in entry_points.iteritems():
        service_cls = entry_point.load()
        service_model = service_cls.get_model()
        setattr(service_model, 'service_type', name)
        setattr(service_model, '_serializer', service_cls.get_serializer())
        setattr(service_model, '_admin_form', service_cls.get_admin_form())
        services.append(service_model)
    return services
