import logging

from django.db import transaction
from django.utils import six

from ceilometerclient import exc as ceilometer_exceptions
from cinderclient import exceptions as cinder_exceptions
from glanceclient import exc as glance_exceptions
from keystoneclient import exceptions as keystone_exceptions
from neutronclient.client import exceptions as neutron_exceptions
from novaclient import exceptions as nova_exceptions

from nodeconductor.structure import ServiceBackend, ServiceBackendError
from nodeconductor.iaas.backend.openstack import OpenStackClient, CloudBackendError
from nodeconductor.iaas.backend.openstack import OpenStackBackend as OldOpenStackBackend
from nodeconductor.openstack import models


logger = logging.getLogger(__name__)


class OpenStackBackendError(ServiceBackendError):
    pass


class OpenStackBackend(ServiceBackend):

    def __init__(self, settings, tenant_id=None):
        credentials = {
            'auth_url': settings.backend_url,
            'username': settings.username,
            'password': settings.password,
        }
        if tenant_id:
            credentials['tenant_id'] = tenant_id
        else:
            credentials['tenant_name'] = settings.options.get('tenant_name', 'admin')

        self.settings = settings
        try:
            self.session = OpenStackClient(dummy=settings.dummy).create_tenant_session(credentials)
        except CloudBackendError as e:
            six.reraise(OpenStackBackendError, e)

        # TODO: Get rid of it (NC-646)
        self._old_backend = OldOpenStackBackend(dummy=self.settings.dummy)

    def __getattr__(self, name):
        methods = ('keystone_client', 'nova_client', 'neutron_client',
                   'cinder_client', 'glance_client', 'ceilometer_client')

        if name in methods:
            return getattr(OpenStackClient, 'create_%s' % name)(self.session)

        return super(OpenStackBackend, self).__getattr__(name)

    def sync(self):
        # Migration status:
        # [x] pull_flavors()
        # [x] pull_images()
        # [ ] pull_service_statistics() (TODO: NC-640)

        try:
            self.pull_flavors()
            self.pull_images()
        except (nova_exceptions.ClientException, glance_exceptions.ClientException) as e:
            logger.exception('Failed to synchronize OpenStack service %s', self.settings.backend_url)
            six.reraise(OpenStackBackendError, e)
        else:
            logger.info('Successfully synchronized OpenStack service %s', self.settings.backend_url)

    def sync_link(self, service_project_link):
        # Migration status:
        # [x] push_membership()
        # [ ] push_security_groups() (TODO: NC-638)
        # [ ] pull_resource_quota() & pull_resource_quota_usage() (TODO: NC-634)

        try:
            self.push_membership(service_project_link)
        except (keystone_exceptions.ClientException, neutron_exceptions.NeutronException) as e:
            logger.exception('Failed to synchronize ServiceProjectLink %s', service_project_link.to_string())
            six.reraise(OpenStackBackendError, e)
        else:
            logger.info('Successfully synchronized ServiceProjectLink %s', service_project_link.to_string())

    def _get_current_properties(self, model):
        return {p.backend_id: p for p in model.objects.filter(settings=self.settings)}

    def pull_flavors(self):
        nova = self.nova_client
        with transaction.atomic():
            cur_flavors = self._get_current_properties(models.Flavor)
            for backend_flavor in nova.flavors.findall(is_public=True):
                cur_flavors.pop(int(backend_flavor.id), None)
                models.Flavor.objects.update_or_create(
                    backend_id=backend_flavor.id,
                    defaults={
                        'name': backend_flavor.name,
                        'cores': backend_flavor.vcpus,
                        'ram': backend_flavor.ram,
                        'disk': self.gb2mb(backend_flavor.disk),
                    })

            map(lambda i: i.delete(), cur_flavors.values())

    def pull_images(self):
        glance = self.glance_client
        with transaction.atomic():
            cur_images = self._get_current_properties(models.Image)
            for backend_image in glance.images.list():
                if backend_image.is_public and not backend_image.deleted:
                    cur_images.pop(backend_image.id, None)
                    models.Image.objects.update_or_create(
                        backend_id=backend_image.id,
                        defaults={
                            'name': backend_image.name,
                            'min_ram': backend_image.min_ram,
                            'min_disk': self.gb2mb(backend_image.min_disk),
                        })

            map(lambda i: i.delete(), cur_images.values())

    def push_membership(self, service_project_link):
        keystone = self.keystone_client
        tenant = self._old_backend.get_or_create_tenant(service_project_link, keystone)

        self.get_or_create_network(service_project_link)

        service_project_link.tenant_id = tenant.id
        service_project_link.save()

    # TODO: (NC-636)
    def get_or_create_network(self, service_project_link):
        pass
