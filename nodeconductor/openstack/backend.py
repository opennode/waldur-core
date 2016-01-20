import calendar
import datetime
import dateutil.parser
import functools
import logging
import re
import sys

from django.db import transaction
from django.utils import six, dateparse, timezone
from requests import ConnectionError

from keystoneclient.auth.identity import v2
from keystoneclient.service_catalog import ServiceCatalog
from keystoneclient import session as keystone_session

from ceilometerclient import client as ceilometer_client
from cinderclient.v1 import client as cinder_client
from glanceclient.v1 import client as glance_client
from keystoneclient.v2_0 import client as keystone_client
from neutronclient.v2_0 import client as neutron_client
from novaclient.v1_1 import client as nova_client

from cinderclient import exceptions as cinder_exceptions
from glanceclient import exc as glance_exceptions
from keystoneclient import exceptions as keystone_exceptions
from neutronclient.client import exceptions as neutron_exceptions
from novaclient import exceptions as nova_exceptions

from nodeconductor.core import NodeConductorExtension
from nodeconductor.core.tasks import send_task
from nodeconductor.structure import ServiceBackend, ServiceBackendError, ServiceBackendNotImplemented
from nodeconductor.structure.log import event_logger
from nodeconductor.openstack import models

from nodeconductor.iaas.backend import CloudBackendError
from nodeconductor.iaas.backend import OpenStackBackend as OldOpenStackBackend


logger = logging.getLogger(__name__)


class OpenStackBackendError(ServiceBackendError):
    pass


class OpenStackSession(dict):
    """ Serializable session """

    def __init__(self, ks_session=None, verify_ssl=True, **credentials):
        self.keystone_session = ks_session

        if not self.keystone_session:
            auth_plugin = v2.Password(**credentials)
            self.keystone_session = keystone_session.Session(auth=auth_plugin, verify=verify_ssl)

        try:
            # This will eagerly sign in throwing AuthorizationFailure on bad credentials
            self.keystone_session.get_token()
        except (keystone_exceptions.AuthorizationFailure, keystone_exceptions.ConnectionRefused) as e:
            six.reraise(OpenStackBackendError, e)

        for opt in ('auth_ref', 'auth_url', 'tenant_id', 'tenant_name'):
            self[opt] = getattr(self.auth, opt)

    def __getattr__(self, name):
        return getattr(self.keystone_session, name)

    @classmethod
    def recover(cls, session, verify_ssl=True):
        if not isinstance(session, dict) or not session.get('auth_ref'):
            raise OpenStackBackendError('Invalid OpenStack session')

        args = {'auth_url': session['auth_url'], 'token': session['auth_ref']['token']['id']}
        if session['tenant_id']:
            args['tenant_id'] = session['tenant_id']
        elif session['tenant_name']:
            args['tenant_name'] = session['tenant_name']

        ks_session = keystone_session.Session(auth=v2.Token(**args), verify=verify_ssl)
        return cls(
            ks_session=ks_session,
            tenant_id=session['tenant_id'],
            tenant_name=session['tenant_name'])

    def validate(self):
        expiresat = dateutil.parser.parse(self.auth.auth_ref['token']['expires'])
        if expiresat > timezone.now() + datetime.timedelta(minutes=10):
            return True

        raise OpenStackBackendError('Invalid OpenStack session')


class OpenStackClient(object):
    """ Generic OpenStack client. """

    def __init__(self, session=None, verify_ssl=False, **credentials):
        if session:
            if isinstance(session, dict):
                logger.info('Trying to recover OpenStack session.')
                self.session = OpenStackSession.recover(session, verify_ssl=verify_ssl)
                self.session.validate()
            else:
                self.session = session
        else:
            try:
                self.session = OpenStackSession(verify_ssl=verify_ssl, **credentials)
            except AttributeError as e:
                logger.error('Failed to create OpenStack session.')
                six.reraise(OpenStackBackendError, e)

    @property
    def keystone(self):
        return keystone_client.Client(session=self.session.keystone_session)

    @property
    def nova(self):
        try:
            return nova_client.Client(session=self.session.keystone_session)
        except (nova_exceptions.ClientException, keystone_exceptions.ClientException) as e:
            logger.exception('Failed to create nova client: %s', e)
            six.reraise(OpenStackBackendError, e)

    @property
    def neutron(self):
        try:
            return neutron_client.Client(session=self.session.keystone_session)
        except (neutron_exceptions.ClientException, keystone_exceptions.ClientException) as e:
            logger.exception('Failed to create neutron client: %s', e)
            six.reraise(OpenStackBackendError, e)

    @property
    def cinder(self):
        try:
            return cinder_client.Client(session=self.session.keystone_session)
        except (cinder_exceptions.ClientException, keystone_exceptions.ClientException) as e:
            logger.exception('Failed to create cinder client: %s', e)
            six.reraise(OpenStackBackendError, e)

    @property
    def glance(self):
        catalog = ServiceCatalog.factory(self.session.auth.auth_ref)
        endpoint = catalog.url_for(service_type='image')

        kwargs = {
            'token': self.session.get_token(),
            'insecure': False,
            'timeout': 600,
            'ssl_compression': True,
        }

        return glance_client.Client(endpoint, **kwargs)

    @property
    def ceilometer(self):
        catalog = ServiceCatalog.factory(self.session.auth.auth_ref)
        endpoint = catalog.url_for(service_type='metering')

        kwargs = {
            'token': lambda: self.session.get_token(),
            'endpoint': endpoint,
            'insecure': False,
            'timeout': 600,
            'ssl_compression': True,
        }

        return ceilometer_client.Client('2', **kwargs)


class OpenStackBackend(ServiceBackend):

    DEFAULT_TENANT = 'admin'

    def __init__(self, settings, tenant_id=None):
        self.settings = settings
        self.tenant_id = tenant_id

        # TODO: Get rid of it (NC-646)
        self._old_backend = OldOpenStackBackend()

    def _get_client(self, name=None, admin=False):
        credentials = {
            'auth_url': self.settings.backend_url,
            'username': self.settings.username,
            'password': self.settings.password,
        }

        if not admin:
            if not self.tenant_id:
                raise OpenStackBackendError(
                    "Can't create tenant session, please provide tenant ID")

            credentials['tenant_id'] = self.tenant_id
        elif self.settings.options:
            credentials['tenant_name'] = self.settings.options.get('tenant_name', self.DEFAULT_TENANT)
        else:
            credentials['tenant_name'] = self.DEFAULT_TENANT

        client = OpenStackClient(**credentials)
        if name:
            return getattr(client, name)
        else:
            return client

    def __getattr__(self, name):
        clients = 'keystone', 'nova', 'neutron', 'cinder', 'glance', 'ceilometer'
        for client in clients:
            if name == '{}_client'.format(client):
                return self._get_client(client, admin=False)

            if name == '{}_admin_client'.format(client):
                return self._get_client(client, admin=True)

        raise AttributeError(
            "'%s' object has no attribute '%s'" % (self.__class__.__name__, name))

    def reraise_exceptions(func):
        @functools.wraps(func)
        def wrapped(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except CloudBackendError as e:
                six.reraise(OpenStackBackendError, e)
        return wrapped

    def ping(self):
        # Session validation occurs on class creation so assume it's active
        # TODO: Consider validating session depending on tenant permissions
        return True

    def ping_resource(self, instance):
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

    def sync_link(self, service_project_link, is_initial=False):
        # Migration status:
        # [x] push_membership()
        # [ ] pull_instances()
        # [x] pull_floating_ips()
        # [x] push_security_groups()
        # [x] pull_resource_quota() & pull_resource_quota_usage()

        try:
            self.push_link(service_project_link)
            self.push_security_groups(service_project_link, is_initial=is_initial)
            self.pull_quotas(service_project_link)
            self.pull_floating_ips(service_project_link)
            self.connect_link_to_external_network(service_project_link)
        except (keystone_exceptions.ClientException, neutron_exceptions.NeutronException) as e:
            logger.exception('Failed to synchronize ServiceProjectLink %s', service_project_link.to_string())
            six.reraise(OpenStackBackendError, e)
        else:
            logger.info('Successfully synchronized ServiceProjectLink %s', service_project_link.to_string())

    def remove_link(self, service_project_link):
        settings = service_project_link.service.settings
        send_task('openstack', 'remove_tenant')(settings.uuid.hex, service_project_link.tenant_id)

    def sync_quotas(self, service_project_link, quotas):
        self.push_quotas(service_project_link, quotas)
        self.pull_quotas(service_project_link)

    def provision(self, instance, flavor=None, image=None, ssh_key=None, **kwargs):
        if ssh_key:
            instance.key_name = ssh_key.name
            instance.key_fingerprint = ssh_key.fingerprint

        instance.flavor_name = flavor.name
        instance.cores = flavor.cores
        instance.ram = flavor.ram
        instance.disk = instance.system_volume_size + instance.data_volume_size
        instance.save()

        send_task('openstack', 'provision')(
            instance.uuid.hex,
            backend_flavor_id=flavor.backend_id,
            backend_image_id=image.backend_id,
            **kwargs)

    def destroy(self, instance, force=False):
        instance.schedule_deletion()
        instance.save()
        send_task('openstack', 'destroy')(instance.uuid.hex, force=force)

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

    def get_key_name(self, public_key):
        # We want names to be human readable in backend.
        # OpenStack only allows latin letters, digits, dashes, underscores and spaces
        # as key names, thus we mangle the original name.

        safe_name = self.sanitize_key_name(public_key.name)
        key_name = '{0}-{1}'.format(public_key.uuid.hex, safe_name)
        return key_name

    def sanitize_key_name(self, key_name):
        # Safe key name length must be less than 17 chars due to limit of full key name to 50 chars.
        return re.sub(r'[^-a-zA-Z0-9 _]+', '_', key_name)[:17]

    def add_ssh_key(self, ssh_key, service_project_link):
        nova = self.nova_client
        key_name = self.get_key_name(ssh_key)

        try:
            nova.keypairs.find(fingerprint=ssh_key.fingerprint)
        except nova_exceptions.NotFound:
            # Fine, it's a new key, let's add it
            logger.info('Propagating ssh public key %s to backend', key_name)
            nova.keypairs.create(name=key_name, public_key=ssh_key.public_key)
            logger.info('Successfully propagated ssh public key %s to backend', key_name)
        else:
            # Found a key with the same fingerprint, skip adding
            logger.info('Skipped propagating ssh public key %s to backend', key_name)

    def remove_ssh_key(self, ssh_key, service_project_link):
        nova = self.nova_client

        # There could be leftovers of key duplicates: remove them all
        keys = nova.keypairs.findall(fingerprint=ssh_key.fingerprint)
        key_name = self.get_key_name(ssh_key)
        for key in keys:
            # Remove only keys created with NC
            if key.name == key_name:
                nova.keypairs.delete(key)

        logger.info('Deleted ssh public key %s from backend', key_name)

    def _get_current_properties(self, model):
        return {p.backend_id: p for p in model.objects.filter(settings=self.settings)}

    def pull_flavors(self):
        nova = self.nova_admin_client
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
        glance = self.glance_admin_client
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

    @reraise_exceptions
    def push_quotas(self, service_project_link, quotas):
        try:
            self._old_backend.push_membership_quotas(service_project_link, quotas)
        except Exception as e:
            event_logger.service_project_link.warning(
                'Failed to push quotas to backend.',
                event_type='service_project_link_sync_failed',
                event_context={
                    'service_project_link': service_project_link,
                    'error_message': six.text_type(e),
                }
            )
            six.reraise(*sys.exc_info())

    @reraise_exceptions
    def pull_quotas(self, service_project_link):
        self._old_backend.pull_resource_quota(service_project_link)
        self._old_backend.pull_resource_quota_usage(service_project_link)

        # additional quotas that are not implemented for in iaas application
        logger.debug('About to get floating ip quota for tenant %s', service_project_link.tenant_id)
        neutron = self.neutron_client
        try:
            floating_ip_count = len(self._old_backend.get_floating_ips(
                tenant_id=service_project_link.tenant_id, neutron=neutron))
            neutron_quotas = neutron.show_quota(tenant_id=service_project_link.tenant_id)['quota']
        except neutron_exceptions.NeutronClientException as e:
            logger.exception('Failed to get floating ip quota for tenant %s', service_project_link.tenant_id)
            six.reraise(OpenStackBackendError, e)
        else:
            logger.info('Successfully got floating ip quota for tenant %s', service_project_link.tenant_id)
            service_project_link.set_quota_usage('floating_ip_count', floating_ip_count)
            service_project_link.set_quota_limit('floating_ip_count', neutron_quotas['floatingip'])

    @reraise_exceptions
    def pull_floating_ips(self, service_project_link):
        try:
            self._old_backend.pull_floating_ips(service_project_link)
        except Exception as e:
            event_logger.service_project_link.warning(
                'Failed to pull floating IPs from backend.',
                event_type='service_project_link_sync_failed',
                event_context={
                    'service_project_link': service_project_link,
                    'error_message': six.text_type(e),
                }
            )
            six.reraise(*sys.exc_info())

    @reraise_exceptions
    def push_security_groups(self, service_project_link, is_initial=False):
        try:
            self._old_backend.push_security_groups(service_project_link, is_membership_creation=is_initial)
        except Exception as e:
            event_logger.service_project_link.warning(
                'Failed to push security groups to backend.',
                event_type='service_project_link_sync_failed',
                event_context={
                    'service_project_link': service_project_link,
                    'error_message': six.text_type(e),
                }
            )
            six.reraise(*sys.exc_info())

    @reraise_exceptions
    def sync_instance_security_groups(self, instance):
        self._old_backend.push_instance_security_groups(instance)

    @reraise_exceptions
    def push_link(self, service_project_link):
        try:
            keystone = self.keystone_admin_client
            tenant = self._old_backend.get_or_create_tenant(service_project_link, keystone)

            service_project_link.tenant_id = self.tenant_id = tenant.id
            service_project_link.save(update_fields=['tenant_id'])

            self._old_backend.ensure_user_is_tenant_admin(self.settings.username, tenant, keystone)
            self.get_or_create_internal_network(service_project_link)
        except Exception as e:
            event_logger.service_project_link.warning(
                'Failed to create service project link on backend.',
                event_type='service_project_link_sync_failed',
                event_context={
                    'service_project_link': service_project_link,
                    'error_message': six.text_type(e),
                }
            )
            six.reraise(*sys.exc_info())

    def get_instance(self, instance_id):
        try:
            nova = self.nova_client
            cinder = self.cinder_client

            instance = nova.servers.get(instance_id)
            try:
                system_volume, data_volume = self._old_backend._get_instance_volumes(nova, cinder, instance_id)
                cores, ram, _ = self._old_backend._get_flavor_info(nova, instance)
                ips = self._old_backend._get_instance_ips(instance)
            except LookupError as e:
                logger.exception("Failed to lookup instance %s information", instance_id)
                six.reraise(OpenStackBackendError, e)

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

                security_groups=[sg['name'] for sg in instance.security_groups],
            )
        except (glance_exceptions.ClientException,
                cinder_exceptions.ClientException,
                nova_exceptions.ClientException,
                neutron_exceptions.NeutronClientException) as e:
            six.reraise(OpenStackBackendError, e)

        return instance

    def get_monthly_cost_estimate(self, instance):
        if not NodeConductorExtension.is_installed('nodeconductor_killbill'):
            raise ServiceBackendNotImplemented

        from nodeconductor_killbill.backend import KillBillBackend, KillBillError

        try:
            backend = KillBillBackend(instance.customer)
            invoice = backend.get_invoice_estimate(instance)
        except KillBillError as e:
            logger.error("Failed to get cost estimate for instance %s: %s", instance, e)
            six.reraise(OpenStackBackendError, e)

        today = datetime.date.today()
        if not invoice['start_date'] <= today <= invoice['end_date']:
            raise OpenStackBackendError("Wrong invoice estimate for instance %s: %s" % (instance, invoice))

        # prorata monthly cost estimate based on daily usage cost
        daily_cost = invoice['amount'] / ((today - invoice['start_date']).days + 1)
        monthly_cost = daily_cost * calendar.monthrange(today.year, today.month)[1]

        return monthly_cost

    def get_resources_for_import(self):
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

    def get_managed_resources(self):
        try:
            ids = [instance.id for instance in self.nova_client.servers.list()]
            return models.Instance.objects.filter(backend_id__in=ids)
        except nova_exceptions.ClientException:
            return []

    def provision_instance(self, instance, backend_flavor_id=None, backend_image_id=None,
                           system_volume_id=None, data_volume_id=None,
                           skip_external_ip_assignment=False):
        logger.info('About to provision instance %s', instance.uuid)
        try:
            nova = self.nova_client
            cinder = self.cinder_client
            neutron = self.neutron_client

            backend_flavor = nova.flavors.get(backend_flavor_id)

            # verify if the internal network to connect to exists
            service_project_link = instance.service_project_link
            try:
                neutron.show_network(service_project_link.internal_network_id)
            except neutron_exceptions.NeutronClientException:
                logger.exception('Internal network with id of %s was not found',
                                 service_project_link.internal_network_id)
                raise OpenStackBackendError('Unable to find network to attach instance to')

            if not skip_external_ip_assignment:
                # TODO: check availability and quota
                self.prepare_floating_ip(service_project_link)
                floating_ip = service_project_link.floating_ips.filter(status='DOWN').first()
                instance.external_ips = floating_ip.address
                floating_ip.status = 'BOOKED'
                floating_ip.save(update_fields=['status'])

            # instance key name and fingerprint are optional
            if instance.key_name:
                safe_key_name = self.sanitize_key_name(instance.key_name)

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

            if not system_volume_id:
                system_volume_name = '{0}-system'.format(instance.name)
                logger.info('Creating volume %s for instance %s', system_volume_name, instance.uuid)
                system_volume = cinder.volumes.create(
                    size=self.mb2gb(instance.system_volume_size),
                    display_name=system_volume_name,
                    display_description='',
                    imageRef=backend_image_id)
                system_volume_id = system_volume.id

            if not data_volume_id:
                data_volume_name = '{0}-data'.format(instance.name)
                logger.info('Creating volume %s for instance %s', data_volume_name, instance.uuid)
                data_volume = cinder.volumes.create(
                    size=self.mb2gb(instance.data_volume_size),
                    display_name=data_volume_name,
                    display_description='')
                data_volume_id = data_volume.id

            if not self._old_backend._wait_for_volume_status(system_volume_id, cinder, 'available', 'error'):
                logger.error(
                    "Failed to provision instance %s: timed out waiting "
                    "for system volume %s to become available",
                    instance.uuid, system_volume_id)
                raise OpenStackBackendError("Timed out waiting for instance %s to provision" % instance.uuid)

            if not self._old_backend._wait_for_volume_status(data_volume_id, cinder, 'available', 'error'):
                logger.error(
                    "Failed to provision instance %s: timed out waiting "
                    "for data volume %s to become available",
                    instance.uuid, data_volume_id)
                raise OpenStackBackendError("Timed out waiting for instance %s to provision" % instance.uuid)

            security_group_ids = instance.security_groups.values_list('security_group__backend_id', flat=True)

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
                        'uuid': system_volume_id,
                        'delete_on_termination': True,
                    },
                    {
                        'destination_type': 'volume',
                        'device_type': 'disk',
                        'source_type': 'volume',
                        'uuid': data_volume_id,
                        'delete_on_termination': True,
                    },
                ],
                nics=[
                    {'net-id': service_project_link.internal_network_id}
                ],
                key_name=backend_public_key.name if backend_public_key is not None else None,
                security_groups=security_group_ids,
            )
            availability_zone = service_project_link.availability_zone
            if availability_zone:
                server_create_parameters['availability_zone'] = availability_zone
            if instance.user_data:
                server_create_parameters['userdata'] = instance.user_data

            server = nova.servers.create(**server_create_parameters)

            instance.backend_id = server.id
            instance.system_volume_id = system_volume_id
            instance.data_volume_id = data_volume_id
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

            self.push_floating_ip_to_instance(instance, server)

        except (glance_exceptions.ClientException,
                cinder_exceptions.ClientException,
                nova_exceptions.ClientException,
                neutron_exceptions.NeutronClientException) as e:
            logger.exception("Failed to provision instance %s", instance.uuid)
            six.reraise(OpenStackBackendError, e)
        else:
            logger.info("Successfully provisioned instance %s", instance.uuid)

    def cleanup(self, dryrun=True):
        # floatingips
        neutron = self.neutron_admin_client
        floatingips = neutron.list_floatingips(tenant_id=self.tenant_id)
        if floatingips:
            for floatingip in floatingips['floatingips']:
                logger.info("Deleting floatingip %s from tenant %s", floatingip['id'], self.tenant_id)
                if not dryrun:
                    neutron.delete_floatingip(floatingip['id'])

        # ports
        ports = neutron.list_ports(tenant_id=self.tenant_id)
        if ports:
            for port in ports['ports']:
                logger.info("Deleting port %s from tenant %s", port['id'], self.tenant_id)
                if not dryrun:
                    neutron.remove_interface_router(port['device_id'], {'port_id': port['id']})

        # routers
        routers = neutron.list_routers(tenant_id=self.tenant_id)
        if routers:
            for router in routers['routers']:
                logger.info("Deleting router %s from tenant %s", router['id'], self.tenant_id)
                if not dryrun:
                    neutron.delete_router(router['id'])

        # networks
        networks = neutron.list_networks(tenant_id=self.tenant_id)
        if networks:
            for network in networks['networks']:
                for subnet in network['subnets']:
                    logger.info("Deleting subnetwork %s from tenant %s", subnet, self.tenant_id)
                    if not dryrun:
                        neutron.delete_subnet(subnet)

                logger.info("Deleting network %s from tenant %s", network['id'], self.tenant_id)
                if not dryrun:
                    neutron.delete_network(network['id'])

        # security groups
        nova = self.nova_client
        sgroups = nova.security_groups.list()
        for sgroup in sgroups:
            logger.info("Deleting security group %s from tenant %s", sgroup.id, self.tenant_id)
            if not dryrun:
                sgroup.delete()

        # servers (instances)
        servers = nova.servers.list()
        for server in servers:
            logger.info("Deleting server %s from tenant %s", server.id, self.tenant_id)
            if not dryrun:
                server.delete()

        # snapshots
        cinder = self.cinder_client
        snapshots = cinder.volume_snapshots.list()
        for snapshot in snapshots:
            logger.info("Deleting snapshots %s from tenant %s", snapshot.id, self.tenant_id)
            if not dryrun:
                snapshot.delete()

        # volumes
        volumes = cinder.volumes.list()
        for volume in volumes:
            logger.info("Deleting volume %s from tenant %s", volume.id, self.tenant_id)
            if not dryrun:
                volume.delete()

        # tenant
        keystone = self.keystone_admin_client
        logger.info("Deleting tenant %s", self.tenant_id)
        if not dryrun:
            keystone.tenants.delete(self.tenant_id)

    def cleanup_instance(self, backend_id=None, external_ips=None, internal_ips=None,
                         system_volume_id=None, data_volume_id=None):

        # instance
        nova = self.nova_client
        nova.servers.delete(backend_id)

        # volumes
        cinder = self.cinder_client
        cinder.volumes.delete(system_volume_id)
        cinder.volumes.delete(data_volume_id)

    @reraise_exceptions
    def update_flavor(self, instance, flavor):
        self._old_backend.update_flavor(instance, flavor)

    @reraise_exceptions
    def extend_disk(self, instance):
        self._old_backend.extend_disk(instance)

    @reraise_exceptions
    def create_security_group(self, security_group):
        nova = self.nova_client
        self._old_backend.create_security_group(security_group, nova)

    @reraise_exceptions
    def delete_security_group(self, security_group):
        nova = self.nova_client
        self._old_backend.delete_security_group(security_group.backend_id, nova)

    @reraise_exceptions
    def update_security_group(self, security_group):
        nova = self.nova_client
        self._old_backend.update_security_group(security_group, nova)

    @reraise_exceptions
    def create_external_network(self, service_project_link, **kwargs):
        neutron = self.neutron_admin_client
        self._old_backend.get_or_create_external_network(service_project_link, neutron, **kwargs)

    @reraise_exceptions
    def detect_external_network(self, service_project_link):
        neutron = self.neutron_admin_client
        self._old_backend.detect_external_network(service_project_link, neutron)

    @reraise_exceptions
    def delete_external_network(self, service_project_link):
        neutron = self.neutron_admin_client
        self._old_backend.delete_external_network(service_project_link, neutron)

    @reraise_exceptions
    def get_or_create_internal_network(self, service_project_link):
        neutron = self.neutron_admin_client
        self._old_backend.get_or_create_internal_network(service_project_link, neutron)

    @reraise_exceptions
    def allocate_floating_ip_address(self, service_project_link):
        neutron = self.neutron_admin_client
        self._old_backend.allocate_floating_ip_address(neutron, service_project_link)

    def prepare_floating_ip(self, service_project_link):
        """ Allocate new floating_ip to service project link tenant if it does not have any free ips """
        if not service_project_link.floating_ips.filter(status='DOWN').exists():
            self.allocate_floating_ip_address(service_project_link)

    @reraise_exceptions
    def assign_floating_ip_to_instance(self, instance, floating_ip):
        nova = self.nova_admin_client
        self._old_backend.assign_floating_ip_to_instance(nova, instance, floating_ip)

    @reraise_exceptions
    def push_floating_ip_to_instance(self, instance, server):
        nova = self.nova_client
        self._old_backend.push_floating_ip_to_instance(server, instance, nova)

    @reraise_exceptions
    def connect_link_to_external_network(self, service_project_link):
        neutron = self.neutron_admin_client
        settings = service_project_link.service.settings
        external_network_id = settings.options.get('external_network_id')
        if external_network_id:
            self._old_backend.connect_membership_to_external_network(
                service_project_link, settings.options['external_network_id'], neutron)
            connected = True
        else:
            logger.warning('OpenStack service project link was not connected to external network: "external_network_id"'
                           ' option is not defined in settings %s option', settings.name)
            connected = False
        return connected

    @reraise_exceptions
    def delete_instance(self, instance):
        try:
            self._old_backend.delete_instance(instance)
            (models.FloatingIP.objects
                .filter(service_project_link=instance.service_project_link, address=instance.external_ips)
                .update(status='DOWN'))
        except:
            event_logger.resource.error(
                'Resource {resource_name} deletion has failed.',
                event_type='resource_deletion_failed',
                event_context={'resource': instance})
            six.reraise(*sys.exc_info())

    @reraise_exceptions
    def create_snapshots(self, service_project_link, volume_ids, prefix='Cloned volume'):
        return self._old_backend.create_snapshots(service_project_link, volume_ids, prefix)

    @reraise_exceptions
    def delete_snapshots(self, service_project_link, snapshot_ids):
        self._old_backend.delete_snapshots(service_project_link, snapshot_ids)

    @reraise_exceptions
    def promote_snapshots_to_volumes(self, service_project_link, snapshot_ids, prefix='Promoted volume'):
        return self._old_backend.promote_snapshots_to_volumes(service_project_link, snapshot_ids, prefix)

    def update_tenant_name(self, service_project_link):
        keystone = self.keystone_admin_client
        self._old_backend.update_tenant_name(service_project_link, keystone)
