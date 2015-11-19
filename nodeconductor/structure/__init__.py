import importlib

from django.conf import settings
from django.utils.lru_cache import lru_cache
from django.utils.encoding import force_text
from rest_framework.reverse import reverse


default_app_config = 'nodeconductor.structure.apps.StructureConfig'


class ServiceTypes(object):
    OpenStack = 1
    DigitalOcean = 2
    Amazon = 3
    Jira = 4
    GitLab = 5
    Oracle = 6
    Azure = 7
    SugarCRM = 8
    SaltStack = 9
    Zabbix = 10

    CHOICES = (
        (OpenStack, 'OpenStack'),
        (DigitalOcean, 'DigitalOcean'),
        (Amazon, 'Amazon'),
        (Jira, 'Jira'),
        (GitLab, 'GitLab'),
        (Oracle, 'Oracle'),
        (Azure, 'Azure'),
        (SugarCRM, 'SugarCRM'),
        (SaltStack, 'SaltStack'),
        (Zabbix, 'Zabbix'),
    )


class SupportedServices(object):
    """ Comprehensive list of currently supported services and resources.
        Build the list via serializers definition on application start.
        Example data structure of registry:

        {
            'gitlab.gitlabservice': {
                'name': 'GitLab',
                'list_view': 'gitlab-list',
                'detail_view': 'gitlab-detail',
                'service_type': 5,
                'backend': nodeconductor_plus.gitlab.backend.GitLabBackend,
                'resources': {
                    'gitlab.group': {
                        'name': 'Group',
                        'list_view': 'gitlab-group-list',
                        'detail_view': 'gitlab-group-detail',
                    },
                    'gitlab.project': {
                        'name': 'Project',
                        'list_view': 'gitlab-project-list',
                        'detail_view': 'gitlab-project-detail',
                    },
                },
            },
        }

    """

    # TODO: Drop support of iaas application
    class Types(ServiceTypes):
        IaaS = -1

        @classmethod
        def get_direct_filter_mapping(cls):
            return tuple((name, name) for _, name in cls.CHOICES)

        @classmethod
        def get_reverse_filter_mapping(cls):
            return {name: code for code, name in cls.CHOICES}

    _registry = {
        'iaas.cloud': {
            'name': 'IaaS',
            'list_view': 'cloud-list',
            'detail_view': 'cloud-detail',
            'service_type': Types.IaaS,
            'backend': NotImplemented,
            'resources': {
                'iaas.instance': {
                    'name': 'Instance',
                    'list_view': 'iaas-resource-list',
                    'detail_view': 'iaas-resource-detail',
                }
            },
        },
    }

    @classmethod
    def register_backend(cls, service_model, backend_class):
        model_str = cls._get_model_srt(service_model)
        cls._registry.setdefault(model_str, {'resources': {}, 'properties': {}})
        cls._registry[model_str]['backend'] = backend_class

        try:
            # Forcely import service serialize to run services auto-discovery
            importlib.import_module(service_model.__module__.replace('models', 'serializers'))
        except ImportError:
            pass

    @classmethod
    def register_service(cls, service_type, metadata):
        if service_type is NotImplemented or not cls._is_active_model(metadata.model):
            return

        model_str = cls._get_model_srt(metadata.model)
        cls._registry.setdefault(model_str, {'resources': {}, 'properties': {}})
        cls._registry[model_str].update({
            'name': dict(cls.Types.CHOICES)[service_type],
            'service_type': service_type,
            'detail_view': metadata.view_name,
            'list_view': metadata.view_name.replace('-detail', '-list'),
        })

    @classmethod
    def register_resource(cls, service, metadata):
        if not service or service.view_name is NotImplemented or not cls._is_active_model(metadata.model):
            return

        model_str = cls._get_model_srt(metadata.model)
        for s in cls._registry:
            if cls._registry[s].get('detail_view') == service.view_name:
                cls._registry[s]['resources'].setdefault(model_str, {})
                cls._registry[s]['resources'][model_str].update({
                    'name': metadata.model.__name__,
                    'detail_view': metadata.view_name,
                    'list_view': metadata.view_name.replace('-detail', '-list'),
                })
                break

    @classmethod
    def register_property(cls, service_type, metadata):
        if service_type is NotImplemented:
            return

        for service_model_name, service in cls._registry.items():
            if service.get('service_type') == service_type:
                model_str = cls._get_model_srt(metadata.model)
                service['properties'][model_str] = {
                    'name': metadata.model.__name__,
                    'list_view': metadata.model.get_url_name() + '-list'
                }
                break

    @classmethod
    def get_service_backend(cls, service_type):
        for service in cls._registry.values():
            if service.get('service_type', 0) == service_type:
                return service['backend']
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
        for service_model_name, service in cls._registry.items():
            service_model = apps.get_model(service_model_name)
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
                5: {
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
        for service_model_name, service in cls._registry.items():
            service_model = apps.get_model(service_model_name)
            service_project_link = cls.get_service_project_link(service_model)
            data[service['service_type']] = {
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
        model_str = cls._get_model_srt(model)
        service = cls._registry[model_str]
        resources = service['resources'].keys()
        return [apps.get_model(resource) for resource in resources]

    @classmethod
    def get_list_view_for_model(cls, model):
        if hasattr(model, 'get_url_name'):
            return model.get_url_name() + '-list'
        return cls._get_view_for_model(model, view_type='list_view')

    @classmethod
    def get_detail_view_for_model(cls, model):
        if hasattr(model, 'get_url_name'):
            return model.get_url_name() + '-detail'
        return cls._get_view_for_model(model, view_type='detail_view')

    @classmethod
    def get_name_for_model(cls, model):
        """ Get a name for given class or model:
            -- it's a service type for a service
            -- it's a <service_type>.<resource_model_name> for a resource
        """
        model_str = cls._get_model_srt(model)
        for model, service in cls._registry.items():
            if model == model_str:
                return service['name']
            for model, resource in service['resources'].items():
                if model == model_str:
                    return '.'.join([service['name'], resource['name']])

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
        model_str = cls._get_model_srt(model)
        for models in cls.get_service_models().values():
            if model_str == cls._get_model_srt(models['service']) or \
               model_str == cls._get_model_srt(models['service_project_link']):
                return models

            for resource_model in models['resources']:
                if model_str == cls._get_model_srt(resource_model):
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
    def _get_model_srt(cls, model):
        return force_text(model._meta)

    @classmethod
    def _get_view_for_model(cls, model, view_type=''):
        if not isinstance(model, basestring):
            model = cls._get_model_srt(model)

        for service_model, service in cls._registry.items():
            if service_model == model:
                return service.get(view_type, None)
            for resource_model, resource in service['resources'].items():
                if resource_model == model:
                    return resource.get(view_type, None)


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

    def get_imported_resources(self):
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
