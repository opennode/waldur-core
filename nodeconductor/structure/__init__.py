import collections
import importlib

from django.conf import settings
from django.utils.lru_cache import lru_cache
from django.utils.encoding import force_text
from rest_framework.reverse import reverse


default_app_config = 'nodeconductor.structure.apps.StructureConfig'


class SupportedServices(object):
    """ Comprehensive list of currently supported services and resources.
        Build the list via serializers definition on application start.
        Example data structure of registry:

        {
            'gitlab': {
                'name': 'GitLab',
                'model_name': 'gitlab.gitlabservice',
                'backend': nodeconductor_plus.gitlab.backend.GitLabBackend,
                'detail_view': 'gitlab-detail',
                'list_view': 'gitlab-list',
                'properties': {},
                'resources': {
                    'gitlab.group': {
                        'name': 'Group',
                        'detail_view': 'gitlab-group-detail',
                        'list_view': 'gitlab-group-list'
                    },
                    'gitlab.project': {
                        'name': 'Project',
                        'detail_view': 'gitlab-project-detail',
                        'list_view': 'gitlab-project-list'
                    }
                }
            }
        }

    """

    class Types(object):
        OpenStack = 'openstack'
        IaaS = 'iaas'

    _registry = collections.defaultdict(lambda: {
        'backend': None,
        'resources': {},
        'properties': {}
    })

    @classmethod
    def get_list_view_for_model(cls, model):
        return model.get_url_name() + '-list'

    @classmethod
    def get_detail_view_for_model(cls, model):
        return model.get_url_name() + '-detail'

    @classmethod
    def register_backend(cls, backend_class):
        from django.apps import apps

        if not cls._is_active_model(backend_class):
            return

        key = cls.get_model_key(backend_class)
        cls._registry[key]['backend'] = backend_class

        try:
            # Forcely import service serialize to run services autodiscovery
            importlib.import_module(backend_class.__module__.replace('backend', 'serializers'))
        except ImportError:
            pass

    @classmethod
    def register_service(cls, model):
        if model is NotImplemented or not cls._is_active_model(model):
            return
        app_config = model._meta.app_config
        key = app_config.label
        cls._registry[key]['name'] = app_config.service_name
        cls._registry[key]['model_name'] = cls._get_model_str(model)
        cls._registry[key]['detail_view'] = cls.get_detail_view_for_model(model)
        cls._registry[key]['list_view'] = cls.get_list_view_for_model(model)

    @classmethod
    def register_resource(cls, model):
        if model is NotImplemented or not cls._is_active_model(model):
            return
        key = cls.get_model_key(model)
        model_str = cls._get_model_str(model)
        cls._registry[key]['resources'][model_str] = {
            'name': model.__name__,
            'detail_view': cls.get_detail_view_for_model(model),
            'list_view': cls.get_list_view_for_model(model)
        }

    @classmethod
    def register_property(cls, model):
        if model is NotImplemented or not cls._is_active_model(model):
            return
        key = cls.get_model_key(model)
        model_str = cls._get_model_str(model)
        cls._registry[key]['properties'][model_str] = {
            'name': model.__name__,
            'list_view': cls.get_list_view_for_model(model)
        }

    @classmethod
    def get_service_backend(cls, key):
        try:
            return cls._registry[key]['backend']
        except IndexError:
            raise ServiceBackendNotImplemented

    @classmethod
    def get_services(cls, request=None):
        """ Get a list of services endpoints.
            {
                "Oracle": "/api/oracle/",
                "OpenStack": "/api/openstack/",
                "GitLab": "/api/gitlab/",
                "DigitalOcean": "/api/digitalocean/"
            }
        """
        return {service['name']: reverse(service['list_view'], request=request)
                for service in cls._registry.values()}

    @classmethod
    def get_resources(cls, request=None):
        """ Get a list of resources endpoints.
            {
                "IaaS.Instance": "/api/iaas-resources/",
                "DigitalOcean.Droplet": "/api/digitalocean-droplets/",
                "Oracle.Database": "/api/oracle-databases/",
                "GitLab.Group": "/api/gitlab-groups/",
                "GitLab.Project": "/api/gitlab-projects/"
            }
        """
        return {'.'.join([service['name'], resource['name']]): reverse(resource['list_view'], request=request)
                for service in cls._registry.values()
                for resource in service['resources'].values()}

    @classmethod
    def get_services_with_resources(cls, request=None):
        """ Get a list of services and resources endpoints.
            {
                ...
                "GitLab": {
                    "url": "/api/gitlab/",
                    "service_project_link_url": "/api/gitlab-service-project-link/",
                    "resources": {
                        "Project": "/api/gitlab-projects/",
                        "Group": "/api/gitlab-groups/"
                    }
                },
                ...
            }
        """
        from django.apps import apps

        data = {}
        for service in cls._registry.values():
            service_model = apps.get_model(service['model_name'])
            service_project_link = cls.get_service_project_link(service_model)
            service_project_link_url = reverse(cls.get_list_view_for_model(service_project_link), request=request)

            data[service['name']] = {
                'url': reverse(service['list_view'], request=request),
                'service_project_link_url': service_project_link_url,
                'resources': {resource['name']: reverse(resource['list_view'], request=request)
                              for resource in service['resources'].values()},
                'properties': {resource['name']: reverse(resource['list_view'], request=request)
                               for resource in service.get('properties', {}).values()}
            }
        return data

    @classmethod
    @lru_cache(maxsize=1)
    def get_service_models(cls):
        """ Get a list of service models.
            {
                ...
                'gitlab': {
                    "service": nodeconductor_plus.gitlab.models.GitLabService,
                    "service_project_link": nodeconductor_plus.gitlab.models.GitLabServiceProjectLink,
                    "resources": [
                        nodeconductor_plus.gitlab.models.Group,
                        nodeconductor_plus.gitlab.models.Project
                    ],
                },
                ...
            }

        """
        from django.apps import apps

        data = {}
        for key, service in cls._registry.items():
            service_model = apps.get_model(service['model_name'])
            service_project_link = cls.get_service_project_link(service_model)
            data[key] = {
                'service': service_model,
                'service_project_link': service_project_link,
                'resources': [apps.get_model(r) for r in service['resources'].keys()],
            }

        return data

    @classmethod
    def get_service_project_link(cls, service_model):
        return next(m[0].model for m in service_model._meta.get_all_related_objects_with_model()
                    if m[0].var_name == 'cloudprojectmembership' or
                    m[0].var_name.endswith('serviceprojectlink'))

    @classmethod
    @lru_cache(maxsize=1)
    def get_resource_models(cls):
        """ Get a list of resource models.
            {
                'DigitalOcean.Droplet': nodeconductor_plus.digitalocean.models.Droplet,
                'GitLab.Group': nodeconductor_plus.gitlab.models.Group,
                'GitLab.Project': nodeconductor_plus.gitlab.models.Project,
                'IaaS.Instance': nodeconductor.iaas.models.Instance,
                'Oracle.Database': nodeconductor.oracle.models.Database
            }

        """
        from django.apps import apps

        return {'.'.join([service['name'], attrs['name']]): apps.get_model(resource)
                for service in cls._registry.values()
                for resource, attrs in service['resources'].items()}

    @classmethod
    @lru_cache(maxsize=1)
    def get_service_resources(cls, model):
        from django.apps import apps

        key = cls.get_model_key(model)
        resources = cls._registry[key]['resources'].keys()
        return [apps.get_model(resource) for resource in resources]

    @classmethod
    def get_name_for_model(cls, model):
        """ Get a name for given class or model:
            -- it's a service type for a service
            -- it's a <service_type>.<resource_model_name> for a resource
        """
        key = cls.get_model_key(model)
        model_str = cls._get_model_str(model)
        service = cls._registry[key]
        if model_str in service['resources']:
            return '{}.{}'.format(service['name'], service['resources'][model_str]['name'])
        else:
            return service['name']

    @classmethod
    def get_related_models(cls, model):
        """ Get a dictionary with related structure models for given class or model:

            >> SupportedServices.get_related_models(gitlab_models.Project)
            {
                'service': nodeconductor_plus.gitlab.models.GitLabService,
                'service_project_link': nodeconductor_plus.gitlab.models.GitLabServiceProjectLink,
                'resources': [
                    nodeconductor_plus.gitlab.models.Group,
                    nodeconductor_plus.gitlab.models.Project,
                ]
            }
        """
        model_str = cls._get_model_str(model)
        for models in cls.get_service_models().values():
            if model_str == cls._get_model_str(models['service']) or \
               model_str == cls._get_model_str(models['service_project_link']):
                return models

            for resource_model in models['resources']:
                if model_str == cls._get_model_str(resource_model):
                    return models

    @classmethod
    def _is_active_model(cls, model):
        """ Check is model app name is in list of INSTALLED_APPS """
        # We need to use such tricky way to check because of inconsistence apps names:
        # some apps are included in format "<module_name>.<app_name>" like "nodeconductor.openstack"
        # other apps are included in format "<app_name>" like "nodecondcutor_sugarcrm"
        return ('.'.join(model.__module__.split('.')[:2]) in settings.INSTALLED_APPS or
                '.'.join(model.__module__.split('.')[:1]) in settings.INSTALLED_APPS)

    @classmethod
    def _get_model_str(cls, model):
        return force_text(model._meta)

    @classmethod
    def get_model_key(cls, model):
        from django.apps import apps
        return apps.get_containing_app_config(model.__module__).label

    @classmethod
    @lru_cache(maxsize=1)
    def get_choices(cls):
        items = [(code, service['name']) for code, service in cls._registry.items()]
        return sorted(items, key=lambda (code, name): name)

    @classmethod
    def get_direct_filter_mapping(cls):
        return tuple((name, name) for _, name in cls.get_choices())

    @classmethod
    def get_reverse_filter_mapping(cls):
        return {name: code for code, name in cls.get_choices()}

    @classmethod
    def has_service_type(cls, service_type):
        return service_type in cls._registry

    @classmethod
    def get_name_for_type(cls, service_type):
        return cls._registry[service_type]['name']

    @classmethod
    @lru_cache(maxsize=1)
    def get_service_settings(cls):
        from django.template.base import TemplateDoesNotExist
        from django.template.loader import render_to_string

        templates = []
        for app, _ in sorted(
                cls._registry.items(),
                key=lambda (app, service): service['name']):
            template_name = '{}/service_settings.html'.format(app)
            try:
                templates.append(render_to_string(template_name))
            except TemplateDoesNotExist:
                pass
        return "\n".join(templates)


class ServiceBackendError(Exception):
    """ Base exception for errors occurring during backend communication. """
    pass


class ServiceBackendNotImplemented(NotImplementedError):
    pass


class ServiceBackend(object):
    """ Basic service backed with only common methods pre-defined. """

    def __init__(self, settings, **kwargs):
        pass

    def ping(self):
        raise ServiceBackendNotImplemented

    def ping_resource(self, resource):
        raise ServiceBackendNotImplemented

    def sync(self):
        raise ServiceBackendNotImplemented

    def sync_link(self, service_project_link, is_initial=False):
        raise ServiceBackendNotImplemented

    def remove_link(self, service_project_link):
        raise ServiceBackendNotImplemented

    def provision(self, resource, *args, **kwargs):
        raise ServiceBackendNotImplemented

    def destroy(self, resource):
        raise ServiceBackendNotImplemented

    def stop(self, resource):
        raise ServiceBackendNotImplemented

    def start(self, resource):
        raise ServiceBackendNotImplemented

    def restart(self, resource):
        raise ServiceBackendNotImplemented

    def add_ssh_key(self, ssh_key, service_project_link):
        raise ServiceBackendNotImplemented

    def remove_ssh_key(self, ssh_key, service_project_link):
        raise ServiceBackendNotImplemented

    def add_user(self, user, service_project_link):
        raise ServiceBackendNotImplemented

    def remove_user(self, user, service_project_link):
        raise ServiceBackendNotImplemented

    def get_resources_for_import(self):
        raise ServiceBackendNotImplemented

    def get_managed_resources(self):
        raise ServiceBackendNotImplemented

    def get_monthly_cost_estimate(self, resource):
        raise ServiceBackendNotImplemented

    @staticmethod
    def gb2mb(val):
        return int(val * 1024) if val else 0

    @staticmethod
    def tb2mb(val):
        return int(val * 1024 * 1024) if val else 0

    @staticmethod
    def mb2gb(val):
        return val / 1024 if val else 0

    @staticmethod
    def mb2tb(val):
        return val / 1024 / 1024 if val else 0
