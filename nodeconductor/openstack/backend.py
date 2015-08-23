import logging

from django.db import transaction
from django.utils import six, dateparse, timezone
from requests import ConnectionError

from ceilometerclient import exc as ceilometer_exceptions
from cinderclient import exceptions as cinder_exceptions
from glanceclient import exc as glance_exceptions
from keystoneclient import exceptions as keystone_exceptions
from neutronclient.client import exceptions as neutron_exceptions
from novaclient import exceptions as nova_exceptions

from nodeconductor.core.tasks import send_task
from nodeconductor.structure import ServiceBackend, ServiceBackendError, ServiceBackendNotImplemented
from nodeconductor.iaas.backend.openstack import OpenStackClient, CloudBackendError
from nodeconductor.iaas.backend.openstack import OpenStackBackend as OldOpenStackBackend
from nodeconductor.openstack import models


logger = logging.getLogger(__name__)


class OpenStackBackendError(ServiceBackendError):
    pass


class OpenStackBackend(ServiceBackend):

    DEFAULT_TENANT = 'admin'

    def __init__(self, settings, tenant_id=None):
        self.settings = settings
        self.is_admin = True

        credentials = {
            'auth_url': settings.backend_url,
            'username': settings.username,
            'password': settings.password,
        }
        if tenant_id:
            self.is_admin = False
            credentials['tenant_id'] = tenant_id
        elif settings.options:
            credentials['tenant_name'] = settings.options.get('tenant_name', self.DEFAULT_TENANT)
        else:
            credentials['tenant_name'] = self.DEFAULT_TENANT

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

    def ping(self):
        # Session validation occurs on class creation so assume it's active
        # TODO: Consider validating session depending on tenant permissions
        return True

    def ping_resource(self, instance):
        if self.is_admin:
            raise ServiceBackendNotImplemented("You have to use tenant session")

        try:
            self.nova_client.servers.get(instance.backend_id)
        except (ConnectionError, nova_exceptions.ClientException):
            return False
        else:
            return True

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
            self.push_link(service_project_link)
        except (keystone_exceptions.ClientException, neutron_exceptions.NeutronException) as e:
            logger.exception('Failed to synchronize ServiceProjectLink %s', service_project_link.to_string())
            six.reraise(OpenStackBackendError, e)
        else:
            logger.info('Successfully synchronized ServiceProjectLink %s', service_project_link.to_string())

    def provision(self, instance, flavor=None, image=None, ssh_key=None):
        if ssh_key:
            instance.key_name = ssh_key.name
            instance.key_fingerprint = ssh_key.fingerprint

        instance.cores = flavor.cores
        instance.ram = flavor.ram
        instance.disk = instance.system_volume_size + instance.data_volume_size
        instance.save()

        send_task('openstack', 'provision')(
            instance.uuid.hex,
            backend_flavor_id=flavor.backend_id,
            backend_image_id=image.backend_id)

    def destroy(self, instance):
        instance.schedule_deletion()
        instance.save()
        send_task('openstack', 'destroy')(instance.uuid.hex)

    def start(self, instance):
        instance.schedule_starting()
        instance.save()
        send_task('openstack', 'start')(instance.uuid.hex)

    def stop(self, instance):
        instance.schedule_stopping()
        instance.save()
        send_task('openstack', 'stop')(instance.uuid.hex)

    def restart(self, instance):
        instance.schedule_restarting()
        instance.save()
        send_task('openstack', 'restart')(instance.uuid.hex)

    def add_ssh_key(self, ssh_key, service_project_link):
        return self._old_backend.remove_ssh_public_key(service_project_link, ssh_key)

    def remove_ssh_key(self, ssh_key, service_project_link):
        return self._old_backend.remove_ssh_public_key(service_project_link, ssh_key)

    def _get_current_properties(self, model):
        return {p.backend_id: p for p in model.objects.filter(settings=self.settings)}

    def pull_flavors(self):
        nova = self.nova_client
        with transaction.atomic():
            cur_flavors = self._get_current_properties(models.Flavor)
            for backend_flavor in nova.flavors.findall(is_public=True):
                cur_flavors.pop(backend_flavor.id, None)
                models.Flavor.objects.update_or_create(
                    settings=self.settings,
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
                        settings=self.settings,
                        backend_id=backend_image.id,
                        defaults={
                            'name': backend_image.name,
                            'min_ram': backend_image.min_ram,
                            'min_disk': self.gb2mb(backend_image.min_disk),
                        })

            map(lambda i: i.delete(), cur_images.values())

    def push_link(self, service_project_link):
        keystone = self.keystone_client
        tenant = self._old_backend.get_or_create_tenant(service_project_link, keystone)

        self._old_backend.ensure_user_is_tenant_admin(self.settings.username, tenant, keystone)
        self.get_or_create_network(service_project_link)

        service_project_link.tenant_id = tenant.id
        service_project_link.save()

    def get_instance(self, instance_id):
        try:
            nova = self.nova_client
            cinder = self.cinder_client

            instance = nova.servers.get(instance_id)
            system_volume, data_volume = self._old_backend._get_instance_volumes(nova, cinder, instance_id)
            cores, ram, _ = self._old_backend._get_flavor_info(nova, instance)
            ips = self._old_backend._get_instance_ips(instance)

            instance.nc_model_data = dict(
                name=instance.name or instance.id,
                key_name=instance.key_name or '',
                start_time=self._old_backend._get_instance_start_time(instance),
                state=self._old_backend._get_instance_state(instance),
                created=dateparse.parse_datetime(instance.created),

                cores=cores,
                ram=ram,
                disk=self.gb2mb(system_volume.size + data_volume.size),

                system_volume_id=system_volume.id,
                system_volume_size=self.gb2mb(system_volume.size),
                data_volume_id=data_volume.id,
                data_volume_size=self.gb2mb(data_volume.size),

                internal_ips=ips.get('internal', ''),
                external_ips=ips.get('external', ''),
            )
        except (glance_exceptions.ClientException,
                cinder_exceptions.ClientException,
                nova_exceptions.ClientException,
                neutron_exceptions.NeutronClientException) as e:
            six.reraise(OpenStackBackendError, e)

        return instance

    def get_resources_for_import(self):
        if self.is_admin:
            raise ServiceBackendNotImplemented(
                "You should use tenant session in order to get resources list")

        cur_instances = models.Instance.objects.all().values_list('backend_id', flat=True)
        try:
            instances = self.nova_client.servers.list()
        except nova_exceptions.ClientException as e:
            six.reraise(OpenStackBackendError, e)
        return [{
            'id': instance.id,
            'name': instance.name or instance.id,
            'created_at': instance.created,
            'status': instance.status,
        } for instance in instances
            if instance.id not in cur_instances and
            self._old_backend._get_instance_state(instance) != models.Instance.States.ERRED]

    def provision_instance(self, instance, backend_flavor_id=None, backend_image_id=None):
        logger.info('About to provision instance %s', instance.uuid)
        try:
            nova = self.nova_client
            cinder = self.cinder_client
            glance = self.glance_client

            backend_flavor = nova.flavors.get(backend_flavor_id)
            backend_image = glance.images.get(backend_image_id)

            # instance key name and fingerprint are optional
            if instance.key_name:
                safe_key_name = self._old_backend.sanitize_key_name(instance.key_name)

                matching_keys = [
                    key
                    for key in nova.keypairs.findall(fingerprint=instance.key_fingerprint)
                    if key.name.endswith(safe_key_name)
                ]
                matching_keys_count = len(matching_keys)

                if matching_keys_count >= 1:
                    if matching_keys_count > 1:
                        # TODO: warning as we trust that fingerprint+name combo is unique.
                        logger.warning(
                            "Found %d public keys with fingerprint %s, "
                            "expected exactly one. Taking the first one.",
                            matching_keys_count, instance.key_fingerprint)
                    backend_public_key = matching_keys[0]
                elif matching_keys_count == 0:
                    logger.error(
                        "Found no public keys with fingerprint %s, expected exactly one",
                        instance.key_fingerprint)
                    # It is possible to fix this situation with OpenStack admin account. So not failing here.
                    # Error log is expected to be addressed.
                    # TODO: consider failing provisioning/putting this check into serializer/pre-save.
                    # reset failed key name/fingerprint
                    instance.key_name = ''
                    instance.key_fingerprint = ''
                    backend_public_key = None
                else:
                    backend_public_key = matching_keys[0]
            else:
                backend_public_key = None

            system_volume_name = '{0}-system'.format(instance.name)
            logger.info('Creating volume %s for instance %s', system_volume_name, instance.uuid)
            system_volume = cinder.volumes.create(
                size=self.mb2gb(instance.system_volume_size),
                display_name=system_volume_name,
                display_description='',
                imageRef=backend_image.id)

            data_volume_name = '{0}-data'.format(instance.name)
            logger.info('Creating volume %s for instance %s', data_volume_name, instance.uuid)
            data_volume = cinder.volumes.create(
                size=self.mb2gb(instance.data_volume_size),
                display_name=data_volume_name,
                display_description='')

            if not self._old_backend._wait_for_volume_status(system_volume.id, cinder, 'available', 'error'):
                logger.error(
                    "Failed to provision instance %s: timed out waiting "
                    "for system volume %s to become available",
                    instance.uuid, system_volume.id)
                raise OpenStackBackendError("Timed out waiting for instance %s to provision" % instance.uuid)

            if not self._old_backend._wait_for_volume_status(data_volume.id, cinder, 'available', 'error'):
                logger.error(
                    "Failed to provision instance %s: timed out waiting "
                    "for data volume %s to become available",
                    instance.uuid, data_volume.id)
                raise OpenStackBackendError("Timed out waiting for instance %s to provision" % instance.uuid)

            server_create_parameters = dict(
                name=instance.name,
                image=None,  # Boot from volume, see boot_index below
                flavor=backend_flavor,
                block_device_mapping_v2=[
                    {
                        'boot_index': 0,
                        'destination_type': 'volume',
                        'device_type': 'disk',
                        'source_type': 'volume',
                        'uuid': system_volume.id,
                        'delete_on_termination': True,
                    },
                    {
                        'destination_type': 'volume',
                        'device_type': 'disk',
                        'source_type': 'volume',
                        'uuid': data_volume.id,
                        'delete_on_termination': True,
                    },
                ],
                key_name=backend_public_key.name if backend_public_key is not None else None,
            )
            availability_zone = instance.service_project_link.availability_zone
            if availability_zone:
                server_create_parameters['availability_zone'] = availability_zone
            if instance.user_data:
                server_create_parameters['userdata'] = instance.user_data

            server = nova.servers.create(**server_create_parameters)

            instance.backend_id = server.id
            instance.system_volume_id = system_volume.id
            instance.data_volume_id = data_volume.id
            instance.save()

            if not self._old_backend._wait_for_instance_status(server.id, nova, 'ACTIVE'):
                logger.error(
                    "Failed to provision instance %s: timed out waiting "
                    "for instance to become online",
                    instance.uuid)
                raise OpenStackBackendError("Timed out waiting for instance %s to provision" % instance.uuid)

            instance.start_time = timezone.now()
            instance.save()

            logger.debug("About to infer internal ip addresses of instance %s", instance.uuid)
            try:
                server = nova.servers.get(server.id)
                fixed_address = server.addresses.values()[0][0]['addr']
            except (nova_exceptions.ClientException, KeyError, IndexError):
                logger.exception(
                    "Failed to infer internal ip addresses of instance %s", instance.uuid)
            else:
                instance.internal_ips = fixed_address
                instance.save()
                logger.info(
                    "Successfully inferred internal ip addresses of instance %s", instance.uuid)

        except (glance_exceptions.ClientException,
                cinder_exceptions.ClientException,
                nova_exceptions.ClientException,
                neutron_exceptions.NeutronClientException) as e:
            logger.exception("Failed to provision instance %s", instance.uuid)
            six.reraise(OpenStackBackendError, e)
        else:
            logger.info("Successfully provisioned instance %s", instance.uuid)

    # TODO: (NC-636)
    def get_or_create_network(self, service_project_link):
        pass
