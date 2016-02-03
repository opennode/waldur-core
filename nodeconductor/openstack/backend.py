import calendar
import datetime
import dateutil.parser
import logging
import re
import sys
import time
import uuid

from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
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
from nodeconductor.core.models import SynchronizationStates
from nodeconductor.core.tasks import send_task
from nodeconductor.structure import ServiceBackend, ServiceBackendError, ServiceBackendNotImplemented
from nodeconductor.structure.log import event_logger
from nodeconductor.openstack import models


logger = logging.getLogger(__name__)


class OpenStackBackendError(ServiceBackendError):
    pass


class OpenStackSession(dict):
    """ Serializable session """

    def __init__(self, ks_session=None, verify_ssl=False, **credentials):
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
    def recover(cls, session, verify_ssl=False):
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

        raise OpenStackBackendError('OpenStack session is expired')


class OpenStackClient(object):
    """ Generic OpenStack client. """

    def __init__(self, session=None, verify_ssl=False, **credentials):
        self.verify_ssl = verify_ssl
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
            'insecure': not self.verify_ssl,
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
            'insecure': not self.verify_ssl,
            'timeout': 600,
            'ssl_compression': True,
        }

        return ceilometer_client.Client('2', **kwargs)


class OpenStackBackend(ServiceBackend):

    DEFAULT_TENANT = 'admin'

    def __init__(self, settings, tenant_id=None):
        self.settings = settings
        self.tenant_id = tenant_id

    def get_client(self, name=None, admin=False):
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

        # Cache session in the object
        attr_name = 'admin_session' if admin else 'session'
        client = getattr(self, attr_name, None)
        if hasattr(self, attr_name):
            client = getattr(self, attr_name)
        else:
            client = OpenStackClient(**credentials)
            setattr(self, attr_name, client)

        if name:
            return getattr(client, name)
        else:
            return client

    def __getattr__(self, name):
        clients = 'keystone', 'nova', 'neutron', 'cinder', 'glance', 'ceilometer'
        for client in clients:
            if name == '{}_client'.format(client):
                return self.get_client(client, admin=False)

            if name == '{}_admin_client'.format(client):
                return self.get_client(client, admin=True)

        raise AttributeError(
            "'%s' object has no attribute '%s'" % (self.__class__.__name__, name))

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

    def _get_instance_state(self, instance):
        # See http://developer.openstack.org/api-ref-compute-v2.html
        nova_to_nodeconductor = {
            'ACTIVE': models.Instance.States.ONLINE,
            'BUILDING': models.Instance.States.PROVISIONING,
            # 'DELETED': models.Instance.States.DELETING,
            # 'SOFT_DELETED': models.Instance.States.DELETING,
            'ERROR': models.Instance.States.ERRED,
            'UNKNOWN': models.Instance.States.ERRED,

            'HARD_REBOOT': models.Instance.States.STOPPING,  # Or starting?
            'REBOOT': models.Instance.States.STOPPING,  # Or starting?
            'REBUILD': models.Instance.States.STARTING,  # Or stopping?

            'PASSWORD': models.Instance.States.ONLINE,
            'PAUSED': models.Instance.States.OFFLINE,

            'RESCUED': models.Instance.States.ONLINE,
            'RESIZED': models.Instance.States.OFFLINE,
            'REVERT_RESIZE': models.Instance.States.STOPPING,
            'SHUTOFF': models.Instance.States.OFFLINE,
            'STOPPED': models.Instance.States.OFFLINE,
            'SUSPENDED': models.Instance.States.OFFLINE,
            'VERIFY_RESIZE': models.Instance.States.OFFLINE,
        }
        return nova_to_nodeconductor.get(instance.status, models.Instance.States.ERRED)

    def _get_tenant_name(self, service_project_link):
        proj = service_project_link.project
        return '%(project_name)s-%(project_uuid)s' % {
            'project_name': ''.join([c for c in proj.name if ord(c) < 128])[:15],
            'project_uuid': proj.uuid.hex[:4]
        }

    def _get_current_properties(self, model):
        return {p.backend_id: p for p in model.objects.filter(settings=self.settings)}

    def _are_rules_equal(self, backend_rule, nc_rule):
        if backend_rule['from_port'] != nc_rule.from_port:
            return False
        if backend_rule['to_port'] != nc_rule.to_port:
            return False
        if backend_rule['ip_protocol'] != nc_rule.protocol:
            return False
        if backend_rule['ip_range'].get('cidr', '') != nc_rule.cidr:
            return False
        return True

    def _are_security_groups_equal(self, backend_security_group, nc_security_group):
        if backend_security_group.name != nc_security_group.name:
            return False
        if len(backend_security_group.rules) != nc_security_group.rules.count():
            return False
        for backend_rule, nc_rule in zip(backend_security_group.rules, nc_security_group.rules.all()):
            if not self._are_rules_equal(backend_rule, nc_rule):
                return False
        return True

    def _normalize_security_group_rule(self, rule):
        if rule['ip_protocol'] is None:
            rule['ip_protocol'] = ''

        if 'cidr' not in rule['ip_range']:
            rule['ip_range']['cidr'] = '0.0.0.0/0'

        return rule

    def _wait_for_instance_status(self, server_id, nova, complete_status,
                                  error_status=None, retries=300, poll_interval=3):
        return self._wait_for_object_status(
            server_id, nova.servers.get, complete_status, error_status, retries, poll_interval)

    def _wait_for_volume_status(self, volume_id, cinder, complete_status,
                                error_status=None, retries=300, poll_interval=3):
        return self._wait_for_object_status(
            volume_id, cinder.volumes.get, complete_status, error_status, retries, poll_interval)

    def _wait_for_snapshot_status(self, snapshot_id, cinder, complete_status, error_status, retries=90, poll_interval=3):
        return self._wait_for_object_status(
            snapshot_id, cinder.volume_snapshots.get, complete_status, error_status, retries, poll_interval)

    def _wait_for_backup_status(self, backup, cinder, complete_status, error_status, retries=90, poll_interval=3):
        return self._wait_for_object_status(
            backup, cinder.backups.get, complete_status, error_status, retries, poll_interval)

    def _wait_for_object_status(self, obj_id, client_get_method, complete_status, error_status=None,
                                retries=30, poll_interval=3):
        complete_state_predicate = lambda o: o.status == complete_status
        if error_status is not None:
            error_state_predicate = lambda o: o.status == error_status
        else:
            error_state_predicate = lambda _: False

        for _ in range(retries):
            obj = client_get_method(obj_id)

            if complete_state_predicate(obj):
                return True

            if error_state_predicate(obj):
                return False

            time.sleep(poll_interval)
        else:
            return False

    def _wait_for_volume_deletion(self, volume_id, cinder, retries=90, poll_interval=3):
        try:
            for _ in range(retries):
                cinder.volumes.get(volume_id)
                time.sleep(poll_interval)

            return False
        except cinder_exceptions.NotFound:
            return True

    def _wait_for_snapshot_deletion(self, snapshot_id, cinder, retries=90, poll_interval=3):
        try:
            for _ in range(retries):
                cinder.volume_snapshots.get(snapshot_id)
                time.sleep(poll_interval)

            return False
        except cinder_exceptions.NotFound:
            return True

    def _wait_for_instance_deletion(self, backend_instance_id, retries=90, poll_interval=3):
        nova = self.nova_client
        try:
            for _ in range(retries):
                nova.servers.get(backend_instance_id)
                time.sleep(poll_interval)

            return False
        except nova_exceptions.NotFound:
            return True

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

            models.Flavor.objects.filter(backend_id__in=cur_flavors.keys()).delete()

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

            models.Image.objects.filter(backend_id__in=cur_images.keys()).delete()

    def push_quotas(self, service_project_link, quotas):
        cinder_quotas = {
            'gigabytes': self.mb2gb(quotas['storage']),
            'volumes': quotas['volumes'],
            'snapshots': quotas['snapshots'],
        }
        nova_quotas = {
            'instances': quotas['instances'],
            'instances': quotas['instances'],
            'cores': quotas['vcpu'],
        }
        neutron_quotas = {
            'security_group': quotas['security_group_count'],
            'security_group_rule': quotas['security_group_rule_count'],
        }

        try:
            self.cinder_client.quotas.update(self.tenant_id, **cinder_quotas)
            self.nova_client.quotas.update(self.tenant_id, **nova_quotas)
            self.neutron_client.update_quota(self.tenant_id, {'quota': neutron_quotas})
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

    def pull_quotas(self, service_project_link):
        nova = self.nova_client
        neutron = self.neutron_client
        cinder = self.cinder_client

        logger.debug('About to get quotas for tenant %s', self.tenant_id)
        try:
            nova_quotas = nova.quotas.get(tenant_id=self.tenant_id)
            cinder_quotas = cinder.quotas.get(tenant_id=self.tenant_id)
            neutron_quotas = neutron.show_quota(tenant_id=self.tenant_id)['quota']
        except (nova_exceptions.ClientException, cinder_exceptions.ClientException) as e:
            logger.exception('Failed to get quotas for tenant %s', self.tenant_id)
            six.reraise(OpenStackBackendError, e)
        else:
            logger.info('Successfully got quotas for tenant %s', self.tenant_id)

        service_project_link.set_quota_limit('ram', nova_quotas.ram)
        service_project_link.set_quota_limit('vcpu', nova_quotas.cores)
        service_project_link.set_quota_limit('storage', self.gb2mb(cinder_quotas.gigabytes))
        service_project_link.set_quota_limit('instances', nova_quotas.instances)
        service_project_link.set_quota_limit('security_group_count', neutron_quotas['security_group'])
        service_project_link.set_quota_limit('security_group_rule_count', neutron_quotas['security_group_rule'])
        service_project_link.set_quota_limit('floating_ip_count', neutron_quotas['floatingip'])

        logger.debug('About to get volumes, snapshots, flavors and instances for tenant %s', self.tenant_id)
        try:
            volumes = cinder.volumes.list()
            snapshots = cinder.volume_snapshots.list()
            instances = nova.servers.list()
            security_groups = nova.security_groups.list()
            floating_ips = neutron.list_floatingips(tenant_id=self.tenant_id)

            flavors = {flavor.id: flavor for flavor in nova.flavors.list()}

            ram, vcpu = 0, 0
            for flavor_id in (instance.flavor['id'] for instance in instances):
                try:
                    flavor = flavors.get(flavor_id, nova.flavors.get(flavor_id))
                except nova_exceptions.NotFound:
                    logger.warning('Cannot find flavor with id %s', flavor_id)
                    continue

                ram += getattr(flavor, 'ram', 0)
                vcpu += getattr(flavor, 'vcpus', 0)

        except (nova_exceptions.ClientException, cinder_exceptions.ClientException) as e:
            logger.exception(
                'Failed to get volumes, snapshots, flavors, '
                'instances or security_groups for tenant %s',
                self.tenant_id)
            six.reraise(OpenStackBackendError, e)
        else:
            logger.info(
                'Successfully got volumes, snapshots, flavors, '
                'instances or security_groups for tenant %s',
                self.tenant_id)

        service_project_link.set_quota_usage('ram', ram)
        service_project_link.set_quota_usage('vcpu', vcpu)
        service_project_link.set_quota_usage('storage', sum(self.gb2mb(v.size) for v in volumes + snapshots))
        service_project_link.set_quota_usage('instances', len(instances), fail_silently=True)
        service_project_link.set_quota_usage('security_group_count', len(security_groups))
        service_project_link.set_quota_usage('security_group_rule_count', len(sum([sg.rules for sg in security_groups], [])))
        service_project_link.set_quota_usage('floating_ip_count', len(floating_ips))

    def pull_floating_ips(self, service_project_link):
        neutron = self.neutron_client
        logger.debug('Pulling floating ips for tenant %s', self.tenant_id)

        try:
            nc_floating_ips = {ip.backend_id: ip for ip in service_project_link.floating_ips.all()}
            try:
                backend_floating_ips = {
                    ip['id']: ip
                    for ip in neutron.list_floatingips(tenant_id=self.tenant_id)['floatingips']
                    if ip.get('floating_ip_address') and ip.get('status')
                }
            except neutron_exceptions.ClientException as e:
                logger.exception('Failed to get a list of floating IPs')
                six.reraise(OpenStackBackendError, e)

            backend_ids = set(backend_floating_ips.keys())
            nc_ids = set(nc_floating_ips.keys())

            with transaction.atomic():
                for ip_id in nc_ids - backend_ids:
                    ip = nc_floating_ips[ip_id]
                    ip.delete()
                    logger.info('Deleted stale floating IP port %s in database', ip.uuid)

                for ip_id in backend_ids - nc_ids:
                    ip = backend_floating_ips[ip_id]
                    created_ip = service_project_link.floating_ips.create(
                        status=ip['status'],
                        backend_id=ip['id'],
                        address=ip['floating_ip_address'],
                        backend_network_id=ip['floating_network_id']
                    )
                    logger.info('Created new floating IP port %s in database', created_ip.uuid)

                for ip_id in nc_ids & backend_ids:
                    nc_ip = nc_floating_ips[ip_id]
                    backend_ip = backend_floating_ips[ip_id]
                    if nc_ip.status != backend_ip['status'] or nc_ip.address != backend_ip['floating_ip_address']\
                            or nc_ip.backend_network_id != backend_ip['floating_network_id']:
                        # If key is BOOKED by NodeConductor it can be still DOWN in OpenStack
                        if not (nc_ip.status == 'BOOKED' and backend_ip['status'] == 'DOWN'):
                            nc_ip.status = backend_ip['status']
                        nc_ip.address = backend_ip['floating_ip_address']
                        nc_ip.backend_network_id = backend_ip['floating_network_id']
                        nc_ip.save()
                        logger.debug('Updated existing floating IP port %s in database', nc_ip.uuid)

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

    def push_security_groups(self, service_project_link, is_initial=False):
        nova = self.nova_client
        logger.debug('About to push security groups for tenant %s', self.tenant_id)

        try:
            nc_security_groups = service_project_link.security_groups.all()
            if not is_initial:
                nc_security_groups = nc_security_groups.filter(
                    state__in=SynchronizationStates.STABLE_STATES)
            try:
                backend_security_groups = {
                    str(g.id): g for g in nova.security_groups.list() if g.name != 'default'}
            except nova_exceptions.ClientException as e:
                logger.exception('Failed to get openstack security groups for tenant %s', self.tenant_id)
                six.reraise(OpenStackBackendError, e)

            # list of nc security groups, that do not exist in openstack
            nonexistent_groups = []
            # list of nc security groups, that have wrong parameters in in openstack
            unsynchronized_groups = []
            # list of os security groups ids, that exist in openstack and do not exist in nc
            extra_group_ids = backend_security_groups.keys()

            for nc_group in nc_security_groups:
                if nc_group.backend_id not in backend_security_groups:
                    nonexistent_groups.append(nc_group)
                else:
                    backend_group = backend_security_groups[nc_group.backend_id]
                    if not self._are_security_groups_equal(backend_group, nc_group):
                        unsynchronized_groups.append(nc_group)
                    extra_group_ids.remove(nc_group.backend_id)

            # deleting extra security groups
            for backend_group_id in extra_group_ids:
                try:
                    nova.security_groups.delete(backend_group_id)
                except nova_exceptions.ClientException as e:
                    logger.exception(
                        'Failed to remove openstack security group with id %s in backend', backend_group_id)

            # updating unsynchronized security groups
            for nc_group in unsynchronized_groups:
                if nc_group.state in SynchronizationStates.STABLE_STATES:
                    nc_group.schedule_syncing()
                    nc_group.save()
                send_task('openstack', 'update_security_group')(nc_group.uuid.hex)

            # creating nonexistent and unsynchronized security groups
            for nc_group in nonexistent_groups:
                if nc_group.state in SynchronizationStates.STABLE_STATES:
                    nc_group.schedule_syncing()
                    nc_group.save()
                send_task('openstack', 'create_security_group')(nc_group.uuid.hex)

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

    def pull_security_groups(self, service_project_link):
        nova = self.nova_client
        logger.debug('About to pull security groups from tenant %s', self.tenant_id)

        try:
            try:
                backend_security_groups = nova.security_groups.list()
            except nova_exceptions.ClientException as e:
                logger.exception('Failed to get openstack security groups for link %s', service_project_link.id)
                six.reraise(OpenStackBackendError, e)

            # list of openstack security groups that do not exist in nc
            nonexistent_groups = []
            # list of openstack security groups that have wrong parameters in in nc
            unsynchronized_groups = []
            # list of nc security groups that do not exist in openstack

            extra_groups = service_project_link.security_groups.exclude(
                backend_id__in=[g.id for g in backend_security_groups],
            )

            with transaction.atomic():
                for backend_group in backend_security_groups:
                    try:
                        nc_group = service_project_link.security_groups.get(backend_id=backend_group.id)
                        if not self._are_security_groups_equal(backend_group, nc_group):
                            unsynchronized_groups.append(backend_group)
                    except models.SecurityGroup.DoesNotExist:
                        nonexistent_groups.append(backend_group)

                # deleting extra security groups
                extra_groups.delete()
                logger.info('Deleted stale security groups in database')

                # synchronizing unsynchronized security groups
                for backend_group in unsynchronized_groups:
                    nc_security_group = service_project_link.security_groups.get(backend_id=backend_group.id)
                    if backend_group.name != nc_security_group.name:
                        nc_security_group.name = backend_group.name
                        nc_security_group.state = SynchronizationStates.IN_SYNC
                        nc_security_group.save()
                    self.pull_security_group_rules(nc_security_group)
                logger.debug('Updated existing security groups in database')

                # creating non-existed security groups
                for backend_group in nonexistent_groups:
                    nc_security_group = service_project_link.security_groups.create(
                        backend_id=backend_group.id,
                        name=backend_group.name,
                        state=SynchronizationStates.IN_SYNC
                    )
                    self.pull_security_group_rules(nc_security_group)
                    logger.info('Created new security group %s in database', nc_security_group.uuid)

        except Exception as e:
            event_logger.service_project_link.warning(
                'Failed to pull security groups from backend.',
                event_type='service_project_link_sync_failed',
                event_context={
                    'service_project_link': service_project_link,
                    'error_message': six.text_type(e),
                }
            )
            six.reraise(*sys.exc_info())

    def pull_security_group_rules(self, security_group):
        nova = self.nova_client
        backend_security_group = nova.security_groups.get(group_id=security_group.backend_id)
        backend_rules = [
            self._normalize_security_group_rule(r)
            for r in backend_security_group.rules
        ]

        # list of openstack rules, that do not exist in nc
        nonexistent_rules = []
        # list of openstack rules, that have wrong parameters in in nc
        unsynchronized_rules = []
        # list of nc rules, that have do not exist in openstack
        extra_rules = security_group.rules.exclude(backend_id__in=[r['id'] for r in backend_rules])

        with transaction.atomic():
            for backend_rule in backend_rules:
                try:
                    nc_rule = security_group.rules.get(backend_id=backend_rule['id'])
                    if not self._are_rules_equal(backend_rule, nc_rule):
                        unsynchronized_rules.append(backend_rule)
                except security_group.rules.model.DoesNotExist:
                    nonexistent_rules.append(backend_rule)

            # deleting extra rules
            extra_rules.delete()
            logger.info('Deleted stale security group rules in database')

            # synchronizing unsynchronized rules
            for backend_rule in unsynchronized_rules:
                security_group.rules.filter(backend_id=backend_rule['id']).update(
                    from_port=backend_rule['from_port'],
                    to_port=backend_rule['to_port'],
                    protocol=backend_rule['ip_protocol'],
                    cidr=backend_rule['ip_range']['cidr'],
                )
            logger.debug('Updated existing security group rules in database')

            # creating non-existed rules
            for backend_rule in nonexistent_rules:
                rule = security_group.rules.create(
                    from_port=backend_rule['from_port'],
                    to_port=backend_rule['to_port'],
                    protocol=backend_rule['ip_protocol'],
                    cidr=backend_rule['ip_range']['cidr'],
                    backend_id=backend_rule['id'],
                )
                logger.info('Created new security group rule %s in database', rule.id)

    def sync_instance_security_groups(self, instance):
        nova = self.nova_client
        server_id = instance.backend_id
        backend_ids = set(g.id for g in nova.servers.list_security_group(server_id))
        nc_ids = set(
            models.SecurityGroup.objects
            .filter(instance_groups__instance__backend_id=server_id)
            .exclude(backend_id='')
            .values_list('backend_id', flat=True)
        )

        # remove stale groups
        for group_id in backend_ids - nc_ids:
            try:
                nova.servers.remove_security_group(server_id, group_id)
            except nova_exceptions.ClientException:
                logger.exception('Failed to remove security group %s from instance %s',
                                 group_id, server_id)
            else:
                logger.info('Removed security group %s from instance %s',
                            group_id, server_id)

        # add missing groups
        for group_id in nc_ids - backend_ids:
            try:
                nova.servers.add_security_group(server_id, group_id)
            except nova_exceptions.ClientException:
                logger.exception('Failed to add security group %s to instance %s',
                                 group_id, server_id)
            else:
                logger.info('Added security group %s to instance %s',
                            group_id, server_id)

    def push_link(self, service_project_link):
        keystone = self.keystone_admin_client

        if service_project_link.tenant_id:
            logger.info('Trying to get connected tenant with id %s', service_project_link.tenant_id)
            try:
                return keystone.tenants.get(service_project_link.tenant_id)
            except keystone_exceptions.NotFound:
                logger.warning('Tenant with id %s does not exist', service_project_link.tenant_id)

        try:
            tenant_name = self._get_tenant_name(service_project_link)
            try:
                tenant = keystone.tenants.create(
                    tenant_name=tenant_name,
                    description=service_project_link.project.description)
            except keystone_exceptions.Conflict:
                tenant = keystone.tenants.find(name=tenant_name)

            service_project_link.tenant_id = self.tenant_id = tenant.id
            service_project_link.save(update_fields=['tenant_id'])

            # Ensure user is tenant admin
            admin_user = keystone.users.find(name=self.settings.username)
            admin_role = keystone.roles.find(name='admin')
            try:
                keystone.roles.add_user_role(
                    user=admin_user.id,
                    role=admin_role.id,
                    tenant=tenant.id)
            except keystone_exceptions.Conflict:
                pass

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
                attached_volume_ids = [v.volumeId for v in nova.volumes.get_server_volumes(instance_id)]
                if len(attached_volume_ids) != 2:
                    raise OpenStackBackendError('Only instances with 2 volumes are supported')

                for volume_id in attached_volume_ids:
                    volume = cinder.volumes.get(volume_id)
                    # Blessed be OpenStack developers for returning booleans as strings
                    if volume.bootable == 'true':
                        system_volume = volume
                    elif volume.bootable == 'false':
                        data_volume = volume

                flavor = nova.flavors.get(instance.flavor['id'])
                cores = flavor.vcpus
                ram = flavor.ram

                ips = {}
                for net_conf in instance.addresses.values():
                    for ip in net_conf:
                        if ip['OS-EXT-IPS:type'] == 'fixed':
                            ips['internal'] = ip['addr']
                        if ip['OS-EXT-IPS:type'] == 'floating':
                            ips['external'] = ip['addr']

            except nova_exceptions.ClientException as e:
                logger.exception("Failed to lookup instance %s information", instance_id)
                six.reraise(OpenStackBackendError, e)

            try:
                d = dateparse.parse_datetime(instance.to_dict()['OS-SRV-USG:launched_at'])
            except (KeyError, ValueError):
                launch_time = None
            else:
                # At the moment OpenStack does not provide any timezone info,
                # but in future it might do.
                if timezone.is_naive(d):
                    launch_time = timezone.make_aware(d, timezone.utc)

            instance.nc_model_data = dict(
                name=instance.name or instance.id,
                key_name=instance.key_name or '',
                start_time=launch_time,
                state=self._get_instance_state(instance),
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
            self._get_instance_state(instance) != models.Instance.States.ERRED]

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

            if not self._wait_for_volume_status(system_volume_id, cinder, 'available', 'error'):
                logger.error(
                    "Failed to provision instance %s: timed out waiting "
                    "for system volume %s to become available",
                    instance.uuid, system_volume_id)
                raise OpenStackBackendError("Timed out waiting for instance %s to provision" % instance.uuid)

            if not self._wait_for_volume_status(data_volume_id, cinder, 'available', 'error'):
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

            if not self._wait_for_instance_status(server.id, nova, 'ACTIVE'):
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

    def extend_disk(self, instance):
        nova = self.nova_client
        cinder = self.cinder_client

        logger.debug('About to extend disk for instance %s', instance.uuid)
        try:
            volume = cinder.volumes.get(instance.data_volume_id)

            server_id = instance.backend_id
            volume_id = volume.id

            new_core_size = instance.data_volume_size
            old_core_size = self.gb2mb(volume.size)
            new_backend_size = self.mb2gb(new_core_size)

            new_core_size_gib = int(round(new_core_size / 1024.0))

            if old_core_size == new_core_size:
                logger.info('Not extending volume %s: it is already of size %d MiB',
                            volume_id, new_core_size)
                return
            elif old_core_size > new_core_size:
                logger.warning('Not extending volume %s: desired size %d MiB is less then current size %d MiB',
                               volume_id, new_core_size, old_core_size)
                event_logger.instance_volume.error(
                    "Virtual machine {instance_name} disk extension has failed "
                    "due to new size being less than old size.",
                    event_type='resource_volume_extension_failed',
                    event_context={'resource': instance}
                )
                return

            nova.volumes.delete_server_volume(server_id, volume_id)
            if not self._wait_for_volume_status(volume_id, cinder, 'available', 'error'):
                logger.error(
                    'Failed to extend volume: timed out waiting volume %s to detach from instance %s',
                    volume_id, instance.uuid,
                )
                raise OpenStackBackendError(
                    'Timed out waiting volume %s to detach from instance %s' % (volume_id, instance.uuid))

            try:
                self._extend_volume(cinder, volume, new_backend_size)
                storage_delta = new_core_size - old_core_size
                instance.service_project_link.add_quota_usage('storage', storage_delta)
            except cinder_exceptions.OverLimit as e:
                logger.warning(
                    'Failed to extend volume: exceeded quota limit while trying to extend volume %s',
                    volume.id,
                )
                event_logger.instance_volume.error(
                    "Virtual machine {instance_name} disk extension has failed due to quota limits.",
                    event_type='resource_volume_extension_failed',
                    event_context={'resource': instance},
                )
                # Reset instance.data_volume_size back so that model reflects actual state
                instance.data_volume_size = old_core_size
                instance.save()

                # Omit logging success
                six.reraise(OpenStackBackendError, e)
            finally:

                nova.volumes.create_server_volume(server_id, volume_id, None)
                if not self._wait_for_volume_status(volume_id, cinder, 'in-use', 'error'):
                    logger.error(
                        'Failed to extend volume: timed out waiting volume %s to attach to instance %s',
                        volume_id, instance.uuid,
                    )
                    raise OpenStackBackendError(
                        'Timed out waiting volume %s to attach to instance %s' % (volume_id, instance.uuid))

        except cinder_exceptions.OverLimit:
            # Omit logging success
            pass
        except (nova_exceptions.ClientException, cinder_exceptions.ClientException) as e:
            logger.exception('Failed to extend disk of an instance %s', instance.uuid)
            six.reraise(OpenStackBackendError, e)
        else:
            logger.info('Successfully extended disk of an instance %s', instance.uuid)
            event_logger.instance_volume.info(
                "Virtual machine {instance_name} disk has been extended to {volume_size} GB.",
                event_type='resource_volume_extension_succeeded',
                event_context={'resource': instance, 'volume_size': new_core_size_gib},
            )

    def push_security_group_rules(self, security_group):
        nova = self.nova_client
        backend_security_group = nova.security_groups.get(group_id=security_group.backend_id)
        backend_rules = {
            rule['id']: self._normalize_security_group_rule(rule)
            for rule in backend_security_group.rules
        }

        # list of nc rules, that do not exist in openstack
        nonexistent_rules = []
        # list of nc rules, that have wrong parameters in in openstack
        unsynchronized_rules = []
        # list of os rule ids, that exist in openstack and do not exist in nc
        extra_rule_ids = backend_rules.keys()

        for nc_rule in security_group.rules.all():
            if nc_rule.backend_id not in backend_rules:
                nonexistent_rules.append(nc_rule)
            else:
                backend_rule = backend_rules[nc_rule.backend_id]
                if not self._are_rules_equal(backend_rule, nc_rule):
                    unsynchronized_rules.append(nc_rule)
                extra_rule_ids.remove(nc_rule.backend_id)

        # deleting extra rules
        for backend_rule_id in extra_rule_ids:
            logger.debug('About to delete security group rule with id %s in backend', backend_rule_id)
            try:
                nova.security_group_rules.delete(backend_rule_id)
            except nova_exceptions.ClientException:
                logger.exception('Failed to remove rule with id %s from security group %s in backend',
                                 backend_rule_id, security_group)
            else:
                logger.info('Security group rule with id %s successfully deleted in backend', backend_rule_id)

        # deleting unsynchronized rules
        for nc_rule in unsynchronized_rules:
            logger.debug('About to delete security group rule with id %s', nc_rule.backend_id)
            try:
                nova.security_group_rules.delete(nc_rule.backend_id)
            except nova_exceptions.ClientException:
                logger.exception('Failed to remove rule with id %s from security group %s in backend',
                                 nc_rule.backend_id, security_group)
            else:
                logger.info('Security group rule with id %s successfully deleted in backend',
                            nc_rule.backend_id)

        # creating nonexistent and unsynchronized rules
        for nc_rule in unsynchronized_rules + nonexistent_rules:
            logger.debug('About to create security group rule with id %s in backend', nc_rule.id)
            try:
                # The database has empty strings instead of nulls
                if nc_rule.protocol == '':
                    nc_rule_protocol = None
                else:
                    nc_rule_protocol = nc_rule.protocol

                nova.security_group_rules.create(
                    parent_group_id=security_group.backend_id,
                    ip_protocol=nc_rule_protocol,
                    from_port=nc_rule.from_port,
                    to_port=nc_rule.to_port,
                    cidr=nc_rule.cidr,
                )
            except nova_exceptions.ClientException as e:
                logger.exception('Failed to create rule %s for security group %s in backend',
                                 nc_rule, security_group)
                six.reraise(OpenStackBackendError, e)
            else:
                logger.info('Security group rule with id %s successfully created in backend', nc_rule.id)

    def create_security_group(self, security_group):
        nova = self.nova_client
        logger.debug('About to create security group %s in backend', security_group.uuid)
        try:
            backend_security_group = nova.security_groups.create(name=security_group.name, description='')
            security_group.backend_id = backend_security_group.id
            security_group.save()
            self.push_security_group_rules(security_group)
        except nova_exceptions.ClientException as e:
            logger.exception('Failed to create openstack security group with for %s in backend', security_group.uuid)
            six.reraise(OpenStackBackendError, e)
        else:
            logger.info('Security group %s successfully created in backend', security_group.uuid)

    def delete_security_group(self, security_group):
        nova = self.nova_client
        logger.debug('About to delete security group %s from backend', security_group.uuid)
        try:
            nova.security_groups.delete(security_group.backend_id)
        except nova_exceptions.ClientException as e:
            logger.exception('Failed to remove openstack security group %s from backend', security_group.uuid)
            six.reraise(OpenStackBackendError, e)
        else:
            logger.info('Security group %s successfully deleted from backend', security_group.uuid)

    def update_security_group(self, security_group):
        nova = self.nova_client
        logger.debug('About to update security group %s in backend', security_group.uuid)
        try:
            backend_security_group = nova.security_groups.find(id=security_group.backend_id)
            if backend_security_group.name != security_group.name:
                nova.security_groups.update(
                    backend_security_group, name=security_group.name, description='')
            self.push_security_group_rules(security_group)
        except nova_exceptions.ClientException as e:
            logger.exception('Failed to update security group %s in backend', security_group.uuid)
            six.reraise(OpenStackBackendError, e)
        else:
            logger.debug('Security group %s successfully updated in backend', security_group.uuid)

    def create_external_network(self, service_project_link, neutron, network_ip, network_prefix,
                                vlan_id=None, vxlan_id=None, ips_count=None):

        if service_project_link.external_network_id:
            self.connect_link_to_external_network(
                service_project_link, service_project_link.external_network_id)

        neutron = self.neutron_admin_client

        # External network creation
        network_name = 'nc-{0}-ext-net'.format(uuid.uuid4().hex)
        network = {
            'name': network_name,
            'tenant_id': service_project_link.tenant_id,
            'router:external': True,
            # XXX: provider:physical_network should be configurable.
            'provider:physical_network': 'physnet1'
        }

        if vlan_id:
            network['provider:network_type'] = 'vlan'
            network['provider:segmentation_id'] = vlan_id
        elif vxlan_id:
            network['provider:network_type'] = 'vxlan'
            network['provider:segmentation_id'] = vxlan_id
        else:
            raise OpenStackBackendError('VLAN or VXLAN ID should be provided.')

        create_response = neutron.create_network({'networks': [network]})
        network_id = create_response['networks'][0]['id']
        logger.info('External network with name %s has been created.', network_name)
        service_project_link.external_network_id = network_id
        service_project_link.save()

        # Subnet creation
        subnet_name = '{0}-sn01'.format(network_name)
        cidr = '{0}/{1}'.format(network_ip, network_prefix)

        subnet_data = {
            'network_id': service_project_link.external_network_id,
            'tenant_id': service_project_link.tenant_id,
            'cidr': cidr,
            'name': subnet_name,
            'ip_version': 4,
            'enable_dhcp': False,
        }
        create_response = neutron.create_subnet({'subnets': [subnet_data]})
        logger.info('Subnet with name %s has been created.', subnet_name)

        # Router creation
        self.get_or_create_router(network_name, create_response['subnets'][0]['id'])

        # Floating IPs creation
        floating_ip = {
            'floating_network_id': service_project_link.external_network_id,
        }

        if vlan_id is not None and ips_count is not None:
            for i in range(ips_count):
                ip = neutron.create_floatingip({'floatingip': floating_ip})['floatingip']
                logger.info('Floating ip %s for external network %s has been created.',
                            ip['floating_ip_address'], network_name)

        return service_project_link.external_network_id

    def detect_external_network(self, service_project_link):
        neutron = self.neutron_admin_client
        routers = neutron.list_routers(tenant_id=service_project_link.tenant_id)['routers']
        if bool(routers):
            router = routers[0]
        else:
            logger.warning('Service project link %s does not have connected routers.', service_project_link)
            return

        ext_gw = router.get('external_gateway_info', {})
        if 'network_id' in ext_gw:
            service_project_link.external_network_id = ext_gw['network_id']
            service_project_link.save()
            logger.info('Found and set external network with id %s', ext_gw['network_id'])

    def delete_external_network(self, service_project_link):
        neutron = self.neutron_admin_client
        floating_ips = neutron.list_floatingips(
            floating_network_id=service_project_link.external_network_id)['floatingips']

        for ip in floating_ips:
            neutron.delete_floatingip(ip['id'])
            logger.info('Floating IP with id %s has been deleted.', ip['id'])

        ports = neutron.list_ports(network_id=service_project_link.external_network_id)['ports']
        for port in ports:
            neutron.remove_interface_router(port['device_id'], {'port_id': port['id']})
            logger.info('Port with id %s has been deleted.', port['id'])

        subnets = neutron.list_subnets(network_id=service_project_link.external_network_id)['subnets']
        for subnet in subnets:
            neutron.delete_subnet(subnet['id'])
            logger.info('Subnet with id %s has been deleted.', subnet['id'])

        neutron.delete_network(service_project_link.external_network_id)
        logger.info('External network with id %s has been deleted.', service_project_link.external_network_id)
        service_project_link.external_network_id = ''
        service_project_link.save()

    def get_or_create_internal_network(self, service_project_link):
        neutron = self.neutron_admin_client
        logger.info('Checking internal network of tenant %s', self.tenant_id)
        if service_project_link.internal_network_id:
            try:
                # check if the network actually exists
                response = neutron.show_network(service_project_link.internal_network_id)
            except neutron_exceptions.NeutronClientException as e:
                logger.exception('Internal network with id %s does not exist. Stale data in database?',
                                 service_project_link.internal_network_id)
                six.reraise(OpenStackBackendError, e)
            else:
                logger.info('Internal network with id %s exists.', service_project_link.internal_network_id)

                network_name = response['network']['name']
                subnet_id = response['network']['subnets'][0]
                self.get_or_create_router(network_name, subnet_id)

            return service_project_link.internal_network_id

        tenant_name = self._get_tenant_name(service_project_link)
        network_name = '{0}-int-net'.format(tenant_name)
        networks = neutron.list_networks(name=network_name)['networks']

        if networks:
            network = networks[0]
            service_project_link.internal_network_id = network['id']
            service_project_link.save()
            logger.info('Internal network %s for tenant %s already exists.', network_name, self.tenant_id)

            subnet_id = network['subnets'][0]
            self.get_or_create_router(network_name, subnet_id)
        else:
            network = {
                'name': network_name,
                'tenant_id': self.tenant_id,
            }

            # in case nothing fits, create and persist internal network
            create_response = neutron.create_network({'networks': [network]})
            network_id = create_response['networks'][0]['id']
            service_project_link.internal_network_id = network_id
            service_project_link.save()
            logger.info('Internal network %s was created for tenant %s.', network_name, self.tenant_id)

            subnet_name = 'nc-{0}-subnet01'.format(network_name)

            logger.info('Creating subnet %s', subnet_name)
            subnet_data = {
                'network_id': service_project_link.internal_network_id,
                'tenant_id': self.tenant_id,
                'cidr': '192.168.42.0/24',
                'allocation_pools': [
                    {
                        'start': '192.168.42.10',
                        'end': '192.168.42.250'
                    }
                ],
                'name': subnet_name,
                'ip_version': 4,
                'enable_dhcp': True,
            }
            create_response = neutron.create_subnet({'subnets': [subnet_data]})
            self.get_or_create_router(network_name, create_response['subnets'][0]['id'])

        return service_project_link.internal_network_id

    def allocate_floating_ip_address(self, service_project_link):
        neutron = self.neutron_admin_client
        try:
            ip_address = neutron.create_floatingip({
                'floatingip': {
                    'floating_network_id': service_project_link.external_network_id,
                    'tenant_id': self.tenant_id,
                }
            })['floatingip']
        except neutron_exceptions.NeutronClientException as e:
            logger.exception('Unable to allocate floating IP address in external network %s',
                             service_project_link.external_network_id)
            six.reraise(OpenStackBackendError, e)
        else:
            service_project_link.floating_ips.create(
                status='DOWN',
                address=ip_address['floating_ip_address'],
                backend_id=ip_address['id'],
                backend_network_id=ip_address['floating_network_id']
            )
            logger.info('Floating IP %s for external network with id %s has been created.',
                        ip_address['floating_ip_address'], service_project_link.external_network_id)

    def prepare_floating_ip(self, service_project_link):
        """ Allocate new floating_ip to service project link tenant if it does not have any free ips """
        if not service_project_link.floating_ips.filter(status='DOWN').exists():
            self.allocate_floating_ip_address(service_project_link)

    def assign_floating_ip_to_instance(self, instance, floating_ip):
        nova = self.nova_admin_client
        nova.servers.add_floating_ip(server=instance.backend_id, address=floating_ip.address)

        floating_ip.status = 'ACTIVE'
        floating_ip.save()

        instance.external_ips = floating_ip.address
        instance.save()

        logger.info('Floating IP %s was successfully assigned to the instance with id %s.',
                    floating_ip.address, instance.uuid)

    def push_floating_ip_to_instance(self, instance, server):
        if not instance.external_ips or not instance.internal_ips:
            return

        logger.debug('About to add external ip %s to instance %s',
                     instance.external_ips, instance.uuid)

        service_project_link = instance.service_project_link
        try:
            floating_ip = service_project_link.floating_ips.get(
                status__in=('BOOKED', 'DOWN'),
                address=instance.external_ips,
                backend_network_id=service_project_link.external_network_id
            )
            server.add_floating_ip(address=instance.external_ips, fixed_address=instance.internal_ips)
        except (
            nova_exceptions.ClientException,
            ObjectDoesNotExist,
            MultipleObjectsReturned,
            KeyError,
            IndexError,
        ):
            logger.exception('Failed to add external ip %s to instance %s',
                             instance.external_ips, instance.uuid)
            instance.set_erred()
            instance.error_message = 'Failed to add external ip %s to instance %s' % (instance.external_ips,
                                                                                      instance.uuid)
            instance.save()
        else:
            floating_ip.status = 'ACTIVE'
            floating_ip.save()
            logger.info('Successfully added external ip %s to instance %s',
                        instance.external_ips, instance.uuid)

    def connect_link_to_external_network(self, service_project_link, external_network_id=None):
        neutron = self.neutron_admin_client

        if not external_network_id:
            options = service_project_link.service.settings.options or {}
            external_network_id = options.get('external_network_id')

        if external_network_id:
            try:
                # check if the network actually exists
                response = neutron.show_network(external_network_id)
            except neutron_exceptions.NeutronClientException as e:
                logger.exception('External network %s does not exist. Stale data in database?', external_network_id)
                six.reraise(OpenStackBackendError, e)

            network_name = response['network']['name']
            subnet_id = response['network']['subnets'][0]
            # XXX: refactor function call, split get_or_create_router into more fine grained
            self.get_or_create_router(network_name, subnet_id,
                                      external=True, network_id=response['network']['id'])

            service_project_link.external_network_id = external_network_id
            service_project_link.save()

            logger.info('Router between external network %s and tenant %s was successfully created',
                        external_network_id, service_project_link.tenant_id)

            return external_network_id

        else:
            logger.warning('OpenStack service project link was not connected to external network: "external_network_id"'
                           ' option is not defined in settings %s option', service_project_link.service.settings.name)
            return None

    def get_or_create_router(self, network_name, subnet_id, external=False, network_id=None):
        neutron = self.neutron_admin_client
        tenant_id = self.tenant_id
        router_name = '{0}-router'.format(network_name)
        routers = neutron.list_routers(tenant_id=tenant_id)['routers']

        if routers:
            logger.info('Router(s) in tenant with id %s already exist(s).', tenant_id)
            router = routers[0]
        else:
            router = neutron.create_router({'router': {'name': router_name, 'tenant_id': tenant_id}})['router']
            logger.info('Router %s has been created.', router['name'])

        try:
            if not external:
                ports = neutron.list_ports(device_id=router['id'], tenant_id=tenant_id)['ports']
                if not ports:
                    neutron.add_interface_router(router['id'], {'subnet_id': subnet_id})
                    logger.info('Internal subnet %s was connected to the router %s.', subnet_id, router_name)
                else:
                    logger.info('Internal subnet %s is already connected to the router %s.', subnet_id, router_name)
            else:
                if (not router.get('external_gateway_info') or
                        router['external_gateway_info'].get('network_id') != network_id):
                    neutron.add_gateway_router(router['id'], {'network_id': network_id})
                    logger.info('External network %s was connected to the router %s.', network_id, router_name)
                else:
                    logger.info('External network %s is already connected to router %s.', network_id, router_name)
        except neutron_exceptions.NeutronClientException as e:
            logger.warning(e)

        return router['id']

    def start_instance(self, instance):
        nova = self.nova_client
        logger.debug('About to start instance %s', instance.uuid)
        try:
            backend_instance = nova.servers.find(id=instance.backend_id)
            backend_instance_state = self._get_instance_state(backend_instance)

            if backend_instance_state == models.Instance.States.ONLINE:
                logger.warning('Instance %s is already started', instance.uuid)
                return

            nova.servers.start(instance.backend_id)

            if not self._wait_for_instance_status(instance.backend_id, nova, 'ACTIVE'):
                logger.error('Failed to start instance %s', instance.uuid)
                event_logger.instance.error(
                    'Virtual machine {instance_name} start has failed.',
                    event_type='resource_start_failed',
                    event_context={'resource': instance})
                raise OpenStackBackendError('Timed out waiting for instance %s to start' % instance.uuid)
        except nova_exceptions.ClientException as e:
            logger.exception('Failed to start instance %s', instance.uuid)
            event_logger.instance.error(
                'Virtual machine {instance_name} start has failed.',
                event_type='resource_start_failed',
                event_context={'resource': instance})
            six.reraise(OpenStackBackendError, e)
        else:
            instance.start_time = timezone.now()
            instance.save(update_fields=['start_time'])

            logger.info('Successfully started instance %s', instance.uuid)
            event_logger.instance.info(
                'Virtual machine {instance_name} has been started.',
                event_type='resource_start_succeeded',
                event_context={'resource': instance})

    def stop_instance(self, instance):
        nova = self.nova_client
        logger.debug('About to stop instance %s', instance.uuid)
        try:
            backend_instance = nova.servers.find(id=instance.backend_id)
            backend_instance_state = self._get_instance_state(backend_instance)

            if backend_instance_state == models.Instance.States.OFFLINE:
                logger.warning('Instance %s is already stopped', instance.uuid)
                return

            nova.servers.stop(instance.backend_id)

            if not self._wait_for_instance_status(instance.backend_id, nova, 'SHUTOFF'):
                logger.error('Failed to stop instance %s', instance.uuid)
                event_logger.instance.error(
                    'Virtual machine {instance_name} stop has failed.',
                    event_type='resource_stop_failed',
                    event_context={'resource': instance})
                raise OpenStackBackendError('Timed out waiting for instance %s to stop' % instance.uuid)
        except nova_exceptions.ClientException as e:
            logger.exception('Failed to stop instance %s', instance.uuid)
            event_logger.instance.error(
                'Virtual machine {instance_name} stop has failed.',
                event_type='resource_stop_failed',
                event_context={'resource': instance})
            six.reraise(OpenStackBackendError, e)
        else:
            instance.start_time = None
            instance.save(update_fields=['start_time'])
            logger.info('Successfully stopped instance %s', instance.uuid)
            event_logger.instance.info(
                'Virtual machine {instance_name} has been stopped.',
                event_type='resource_stop_succeeded',
                event_context={'resource': instance})

    def restart_instance(self, instance):
        nova = self.nova_client
        logger.debug('About to restart instance %s', instance.uuid)
        try:
            nova.servers.reboot(instance.backend_id)

            if not self._wait_for_instance_status(instance.backend_id, nova, 'ACTIVE', retries=80):
                logger.error('Failed to restart instance %s', instance.uuid)
                event_logger.instance.error(
                    'Virtual machine {instance_name} restart has failed.',
                    event_type='resource_restart_failed',
                    event_context={'resource': instance})
                raise OpenStackBackendError('Timed out waiting for instance %s to restart' % instance.uuid)
        except nova_exceptions.ClientException as e:
            logger.exception('Failed to restart instance %s', instance.uuid)
            event_logger.instance.error(
                'Virtual machine {instance_name} restart has failed.',
                event_type='resource_restart_failed',
                event_context={'resource': instance})
            six.reraise(OpenStackBackendError, e)
        else:
            logger.info('Successfully restarted instance %s', instance.uuid)
            event_logger.instance.info(
                'Virtual machine {instance_name} has been restarted.',
                event_type='resource_restart_succeeded',
                event_context={'resource': instance})

    def delete_instance(self, instance):
        nova = self.nova_client
        logger.info('About to delete instance %s', instance.uuid)
        try:
            nova.servers.delete(instance.backend_id)

            if not self._wait_for_instance_deletion(instance.backend_id):
                logger.info('Failed to delete instance %s', instance.uuid)
                event_logger.instance.error(
                    'Virtual machine {instance_name} deletion has failed.',
                    event_type='resource_deletion_failed',
                    event_context={'resource': instance})
                raise OpenStackBackendError('Timed out waiting for instance %s to get deleted' % instance.uuid)

        except nova_exceptions.ClientException as e:
            logger.info('Failed to delete instance %s', instance.uuid)
            event_logger.instance.error(
                'Virtual machine {instance_name} deletion has failed.',
                event_type='resource_deletion_failed',
                event_context={'resource': instance})
            six.reraise(OpenStackBackendError, e)
        else:
            logger.info('Successfully deleted instance %s', instance.uuid)
            event_logger.instance.info(
                'Virtual machine {instance_name} has been deleted.',
                event_type='resource_deletion_succeeded',
                event_context={'resource': instance})

            if instance.service_project_link.floating_ips.filter(address=instance.external_ips).update(status='DOWN'):
                logger.info('Successfully released floating ip %s from instance %s',
                            instance.external_ips, instance.uuid)

    def create_snapshots(self, service_project_link, volume_ids, prefix='Cloned volume'):
        cinder = self.cinder_client
        logger.debug('About to snapshot volumes %s', ', '.join(volume_ids))
        try:
            snapshot_ids = []
            for volume_id in volume_ids:
                # create a temporary snapshot
                snapshot = self.create_snapshot(volume_id, cinder)
                service_project_link.add_quota_usage('storage', self.gb2mb(snapshot.size))
                snapshot_ids.append(snapshot.id)

        except (cinder_exceptions.ClientException, keystone_exceptions.ClientException) as e:
            logger.exception('Failed to snapshot volumes %s', ', '.join(volume_ids))
            six.reraise(OpenStackBackendError, e)
        else:
            logger.info('Successfully created snapshots %s for volumes.', ', '.join(snapshot_ids))
        return snapshot_ids

    def delete_snapshots(self, service_project_link, snapshot_ids):
        cinder = self.cinder_client
        logger.debug('About to delete volumes %s ', ', '.join(snapshot_ids))
        try:
            for snapshot_id in snapshot_ids:
                logger.debug('About to delete a snapshot %s', snapshot_id)

                # volume
                size = cinder.volume_snapshots.get(snapshot_id).size
                if not self._wait_for_snapshot_status(snapshot_id, cinder, 'available', 'error', poll_interval=60, retries=30):
                    raise OpenStackBackendError('Timed out waiting for snapshot %s to become available', snapshot_id)

                cinder.volume_snapshots.delete(snapshot_id)

                if self._wait_for_snapshot_deletion(snapshot_id, cinder):
                    service_project_link.add_quota_usage('storage', -self.gb2mb(size))
                    logger.info('Successfully deleted a snapshot %s', snapshot_id)
                else:
                    logger.exception('Failed to delete snapshot %s', snapshot_id)

        except (cinder_exceptions.ClientException, keystone_exceptions.ClientException) as e:
            logger.exception(
                'Failed to delete snapshots %s', ', '.join(snapshot_ids))
            six.reraise(OpenStackBackendError, e)
        else:
            logger.info(
                'Successfully deleted snapshots %s', ', '.join(snapshot_ids))

    def create_volume_from_snapshot(self, snapshot_id, prefix='Promoted volume'):
        cinder = self.cinder_client
        snapshot = cinder.volume_snapshots.get(snapshot_id)
        volume_size = snapshot.size
        volume_name = prefix + (' %s' % snapshot.volume_id)

        logger.debug('About to create temporary volume from snapshot %s', snapshot_id)
        created_volume = cinder.volumes.create(volume_size, snapshot_id=snapshot_id,
                                               display_name=volume_name)
        volume_id = created_volume.id

        if not self._wait_for_volume_status(volume_id, cinder, 'available', 'error'):
            raise OpenStackBackendError('Timed out creating temporary volume from snapshot %s', snapshot_id)

        logger.info('Successfully created temporary volume %s from snapshot %s',
                    volume_id, snapshot_id)

        return volume_id

    def promote_snapshots_to_volumes(self, service_project_link, snapshot_ids, prefix='Promoted volume'):
        cinder = self.cinder_client
        logger.debug('About to promote snapshots %s', ', '.join(snapshot_ids))
        try:
            promoted_volume_ids = []
            for snapshot_id in snapshot_ids:
                # volume
                snapshot = cinder.volume_snapshots.get(snapshot_id)
                promoted_volume_id = self.create_volume_from_snapshot(snapshot_id, prefix=prefix)
                promoted_volume_ids.append(promoted_volume_id)
                # volume size should be equal to a snapshot size
                service_project_link.add_quota_usage('storage', self.gb2mb(snapshot.size))

        except (cinder_exceptions.ClientException, keystone_exceptions.ClientException) as e:
            logger.exception('Failed to promote snapshots %s', ', '.join(snapshot_ids))
            six.reraise(OpenStackBackendError, e)
        else:
            logger.info('Successfully promoted volumes %s', ', '.join(promoted_volume_ids))
        return promoted_volume_ids

    def update_tenant_name(self, service_project_link):
        keystone = self.keystone_admin_client
        tenant_name = self._get_tenant_name(service_project_link)

        if service_project_link.tenant_id:
            logger.info('Trying to update name for tenant with id %s', service_project_link.tenant_id)
            try:
                keystone.tenants.update(service_project_link.tenant_id, name=tenant_name)
                logger.info("Successfully updated name for tenant with id %s. Tenant's new name is %s",
                            service_project_link.tenant_id, tenant_name)
            except keystone_exceptions.NotFound as e:
                logger.warning('Tenant with id %s does not exist', service_project_link.tenant_id)
                six.reraise(OpenStackBackendError, e)
        else:
            logger.warning('Cannot update tenant name for link %s without tenant ID', service_project_link)
