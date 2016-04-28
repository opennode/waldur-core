import datetime
import dateutil.parser
import logging
import re
import time
import uuid

from django.conf import settings as django_settings
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
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

from nodeconductor.core.models import StateMixin
from nodeconductor.core.tasks import send_task
from nodeconductor.structure import ServiceBackend, ServiceBackendError, log_backend_action
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

    def __str__(self):
        return str({k: v if k != 'password' else '***' for k, v in self})


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
        except (neutron_exceptions.NeutronClientException, keystone_exceptions.ClientException) as e:
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

    def ping(self, raise_exception=False):
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

    def provision(self, instance, flavor=None, image=None, ssh_key=None, **kwargs):
        if ssh_key:
            instance.key_name = self.get_key_name(ssh_key)
            instance.key_fingerprint = ssh_key.fingerprint
            kwargs['public_key'] = ssh_key.public_key

        instance.flavor_name = flavor.name
        instance.cores = flavor.cores
        instance.ram = flavor.ram
        instance.flavor_disk = flavor.disk
        instance.disk = instance.system_volume_size + instance.data_volume_size
        if image:
            instance.image_name = image.name
            instance.min_disk = image.min_disk
            instance.min_ram = image.min_ram
        instance.save()

        kwargs['backend_flavor_id'] = flavor.backend_id
        if image:
            kwargs['backend_image_id'] = image.backend_id

        send_task('openstack', 'provision')(instance.uuid.hex, **kwargs)

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
        if service_project_link.tenant is not None:
            key_name = self.get_key_name(ssh_key)
            self.get_or_create_ssh_key_for_tenant(
                service_project_link.tenant, key_name, ssh_key.fingerprint, ssh_key.public_key)

    def get_or_create_ssh_key_for_tenant(self, tenant, key_name, fingerprint, public_key):
        nova = self.nova_client

        try:
            return nova.keypairs.find(fingerprint=fingerprint)
        except nova_exceptions.NotFound:
            # Fine, it's a new key, let's add it
            try:
                return nova.keypairs.create(name=key_name, public_key=public_key)
            except (nova_exceptions.ClientException, keystone_exceptions.ClientException) as e:
                six.reraise(OpenStackBackendError, e)
            else:
                logger.info('Propagating ssh public key %s to backend', key_name)
        except (nova_exceptions.ClientException, keystone_exceptions.ClientException) as e:
            six.reraise(OpenStackBackendError, e)
        else:
            # Found a key with the same fingerprint, skip adding
            logger.info('Skipped propagating ssh public key %s to backend', key_name)

    def remove_ssh_key(self, ssh_key, service_project_link):
        if service_project_link.tenant is not None:
            self.remove_ssh_key_from_tenant(service_project_link.tenant, ssh_key)

    @log_backend_action()
    def remove_ssh_key_from_tenant(self, tenant, key_name, fingerprint):
        nova = self.nova_client

        # There could be leftovers of key duplicates: remove them all
        keys = nova.keypairs.findall(fingerprint=fingerprint)
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
        except (cinder_exceptions.NotFound, keystone_exceptions.NotFound):
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

    @log_backend_action('push quotas for tenant')
    def push_tenant_quotas(self, tenant, quotas):
        if 'instances' in quotas:
            # convert instances quota to volumes and snapshots.
            quotas_ratios = django_settings.NODECONDUCTOR.get('OPENSTACK_QUOTAS_INSTANCE_RATIOS', {})
            volume_ratio = quotas_ratios.get('volumes', 4)
            snapshots_ratio = quotas_ratios.get('snapshots', 20)

            quotas['volumes'] = volume_ratio * quotas['instances']
            quotas['snapshots'] = snapshots_ratio * quotas['instances']

        cinder_quotas = {
            'gigabytes': self.mb2gb(quotas.get('storage')) if 'storage' in quotas else None,
            'volumes': quotas.get('volumes'),
            'snapshots': quotas.get('snapshots'),
        }
        cinder_quotas = {k: v for k, v in cinder_quotas.items() if v is not None}

        nova_quotas = {
            'instances': quotas.get('instances'),
            'cores': quotas.get('vcpu'),
        }
        nova_quotas = {k: v for k, v in nova_quotas.items() if v is not None}

        neutron_quotas = {
            'security_group': quotas.get('security_group_count'),
            'security_group_rule': quotas.get('security_group_rule_count'),
        }
        neutron_quotas = {k: v for k, v in neutron_quotas.items() if v is not None}

        try:
            if cinder_quotas:
                self.cinder_client.quotas.update(tenant.backend_id, **cinder_quotas)
            if nova_quotas:
                self.nova_client.quotas.update(tenant.backend_id, **nova_quotas)
            if neutron_quotas:
                self.neutron_client.update_quota(tenant.backend_id, {'quota': neutron_quotas})
        except Exception as e:
            six.reraise(OpenStackBackendError, e)

    @log_backend_action('pull quotas for tenant')
    def pull_tenant_quotas(self, tenant):
        # XXX: backend quotas should be moved to tenant from SPL in future.
        nova = self.nova_client
        neutron = self.neutron_client
        cinder = self.cinder_client
        service_project_link = tenant.service_project_link

        try:
            nova_quotas = nova.quotas.get(tenant_id=tenant.backend_id)
            cinder_quotas = cinder.quotas.get(tenant_id=tenant.backend_id)
            neutron_quotas = neutron.show_quota(tenant_id=tenant.backend_id)['quota']
        except (nova_exceptions.ClientException,
                cinder_exceptions.ClientException,
                neutron_exceptions.NeutronClientException) as e:
            six.reraise(OpenStackBackendError, e)

        service_project_link.set_quota_limit('ram', nova_quotas.ram)
        service_project_link.set_quota_limit('vcpu', nova_quotas.cores)
        service_project_link.set_quota_limit('storage', self.gb2mb(cinder_quotas.gigabytes))
        service_project_link.set_quota_limit('instances', nova_quotas.instances)
        service_project_link.set_quota_limit('security_group_count', neutron_quotas['security_group'])
        service_project_link.set_quota_limit('security_group_rule_count', neutron_quotas['security_group_rule'])
        service_project_link.set_quota_limit('floating_ip_count', neutron_quotas['floatingip'])

        try:
            volumes = cinder.volumes.list()
            snapshots = cinder.volume_snapshots.list()
            instances = nova.servers.list()
            security_groups = nova.security_groups.list()
            floating_ips = neutron.list_floatingips(tenant_id=tenant.backend_id)['floatingips']

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

        except (nova_exceptions.ClientException,
                cinder_exceptions.ClientException,
                neutron_exceptions.NeutronClientException) as e:
            six.reraise(OpenStackBackendError, e)

        service_project_link.set_quota_usage('ram', ram)
        service_project_link.set_quota_usage('vcpu', vcpu)
        service_project_link.set_quota_usage('storage', sum(self.gb2mb(v.size) for v in volumes + snapshots))
        service_project_link.set_quota_usage('instances', len(instances), fail_silently=True)
        service_project_link.set_quota_usage('security_group_count', len(security_groups))
        service_project_link.set_quota_usage('security_group_rule_count', len(sum([sg.rules for sg in security_groups], [])))
        service_project_link.set_quota_usage('floating_ip_count', len(floating_ips))

    @log_backend_action('pull floating IPs for tenant')
    def pull_tenant_floating_ips(self, tenant):
        service_project_link = tenant.service_project_link
        neutron = self.neutron_client

        try:
            nc_floating_ips = {ip.backend_id: ip for ip in service_project_link.floating_ips.all()}
            try:
                backend_floating_ips = {
                    ip['id']: ip
                    for ip in neutron.list_floatingips(tenant_id=self.tenant_id)['floatingips']
                    if ip.get('floating_ip_address') and ip.get('status')
                }
            except neutron_exceptions.NeutronClientException as e:
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
                        logger.info('Updated existing floating IP port %s in database', nc_ip.uuid)

        except Exception as e:
            six.reraise(OpenStackBackendError, e)

    @log_backend_action('pull security groups for tenant')
    def pull_tenant_security_groups(self, tenant):
        nova = self.nova_client
        service_project_link = tenant.service_project_link

        try:
            try:
                backend_security_groups = nova.security_groups.list()
            except nova_exceptions.ClientException as e:
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
                if extra_groups:
                    logger.debug('Deleted stale security group: %s.',
                                 ' ,'.join('%s (PK: %s)' % (sg.name, sg.pk) for sg in extra_groups))

                # synchronizing unsynchronized security groups
                for backend_group in unsynchronized_groups:
                    nc_security_group = service_project_link.security_groups.get(backend_id=backend_group.id)
                    if backend_group.name != nc_security_group.name:
                        nc_security_group.name = backend_group.name
                        nc_security_group.state = StateMixin.States.OK
                        nc_security_group.save()
                    self.pull_security_group_rules(nc_security_group)
                    logger.debug('Updated existing security group %s (PK: %s).',
                                 nc_security_group.name, nc_security_group.pk)

                # creating non-existed security groups
                for backend_group in nonexistent_groups:
                    nc_security_group = service_project_link.security_groups.create(
                        backend_id=backend_group.id,
                        name=backend_group.name,
                        state=StateMixin.States.OK
                    )
                    self.pull_security_group_rules(nc_security_group)
                    logger.debug('Created new security group %s (PK: %s).',
                                 nc_security_group.name, nc_security_group.pk)

        except Exception as e:
            six.reraise(OpenStackBackendError, e)

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

    @log_backend_action()
    def create_tenant(self, tenant):
        keystone = self.keystone_admin_client
        try:
            backend_tenant = keystone.tenants.create(tenant_name=tenant.name, description=tenant.description)
            tenant.backend_id = backend_tenant.id
            tenant.save(update_fields=['backend_id'])
        except keystone_exceptions.ClientException as e:
            six.reraise(OpenStackBackendError, e)

    @log_backend_action()
    def pull_tenant(self, tenant):
        keystone = self.keystone_admin_client
        if not tenant.backend_id:
            raise OpenStackBackendError('Cannot pull tenant without backend_id')
        try:
            backend_tenant = keystone.tenants.get(tenant.backend_id)
        except keystone_exceptions.ClientException as e:
            six.reraise(OpenStackBackendError, e)
        else:
            tenant.name = backend_tenant.name
            tenant.description = backend_tenant.description
            tenant.save()

    @log_backend_action()
    def add_admin_user_to_tenant(self, tenant):
        """ Add user from openstack settings to new tenant """
        keystone = self.keystone_admin_client

        try:
            admin_user = keystone.users.find(name=self.settings.username)
            admin_role = keystone.roles.find(name='admin')
            try:
                keystone.roles.add_user_role(
                    user=admin_user.id,
                    role=admin_role.id,
                    tenant=tenant.backend_id)
            except keystone_exceptions.Conflict:
                pass
        except keystone_exceptions.ClientException as e:
            six.reraise(OpenStackBackendError, e)

    @log_backend_action('add user to tenant')
    def create_tenant_user(self, tenant):
        keystone = self.keystone_client

        try:
            user = keystone.users.create(
                name=tenant.user_username,
                password=tenant.user_password,
            )
            admin_role = keystone.roles.find(name='Member')
            keystone.roles.add_user_role(
                user=user.id,
                role=admin_role.id,
                tenant=tenant.backend_id,
            )
        except keystone_exceptions.ClientException as e:
            six.reraise(OpenStackBackendError, e)

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
                           skip_external_ip_assignment=False, public_key=None):
        logger.info('About to provision instance %s', instance.uuid)
        try:
            nova = self.nova_client
            cinder = self.cinder_client
            neutron = self.neutron_client

            backend_flavor = nova.flavors.get(backend_flavor_id)

            # verify if the internal network to connect to exists
            service_project_link = instance.service_project_link
            # XXX: In the future instance should depend on tenant. Now SPL can have only one tenant.
            tenant = service_project_link.tenant
            try:
                neutron.show_network(service_project_link.internal_network_id)
            except neutron_exceptions.NeutronClientException:
                logger.exception('Internal network with id of %s was not found',
                                 service_project_link.internal_network_id)
                raise OpenStackBackendError('Unable to find network to attach instance to')

            if not skip_external_ip_assignment:
                # TODO: check availability and quota
                if not service_project_link.floating_ips.filter(status='DOWN').exists():
                    self.allocate_floating_ip_address(tenant)
                floating_ip = service_project_link.floating_ips.filter(status='DOWN').first()
                instance.external_ips = floating_ip.address
                floating_ip.status = 'BOOKED'
                floating_ip.save(update_fields=['status'])

            # instance key name and fingerprint are optional
            if instance.key_name:
                backend_public_key = self.get_or_create_ssh_key_for_tenant(
                    tenant, instance.key_name, instance.key_fingerprint, public_key)
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

            backend_security_groups = server.list_security_group()
            for bsg in backend_security_groups:
                if instance.security_groups.filter(security_group__name=bsg.name).exists():
                    continue
                try:
                    security_group = service_project_link.security_groups.get(name=bsg.name)
                except models.SecurityGroup.DoesNotExist:
                    logger.error(
                        'SPL %s (PK: %s) does not have security group "%s", but its instance %s (PK: %s) has.' %
                        (service_project_link, service_project_link.pk, bsg.name, instance, instance.pk)
                    )
                else:
                    instance.security_groups.create(security_group=security_group)

        except (glance_exceptions.ClientException,
                cinder_exceptions.ClientException,
                nova_exceptions.ClientException,
                neutron_exceptions.NeutronClientException) as e:
            logger.exception("Failed to provision instance %s", instance.uuid)
            six.reraise(OpenStackBackendError, e)
        else:
            logger.info("Successfully provisioned instance %s", instance.uuid)

    @log_backend_action('pull instances for tenant')
    def pull_tenant_instances(self, tenant):
        spl = tenant.service_project_link
        States = models.Instance.States
        for instance in spl.instances.filter(state__in=[States.ONLINE, States.OFFLINE]):
            try:
                instance_data = self.get_instance(instance.backend_id).nc_model_data
            except OpenStackBackendError as e:
                logger.error('Cannot get data for instance %s (PK: %s). Error: %s', instance, instance.pk, e)
            else:
                instance.ram = instance_data['ram']
                instance.cores = instance_data['cores']
                instance.disk = instance_data['disk']
                instance.system_volume_size = instance_data['system_volume_size']
                instance.data_volume_size = instance_data['data_volume_size']
                instance.save()
                logger.info('Instance %s (PK: %s) has been successfully pulled from OpenStack.', instance, instance.pk)

    # XXX: This method should be deleted after tenant separation from SPL.
    def cleanup(self, dryrun=True):
        if not self.tenant_id:
            logger.info("Nothing to cleanup, tenant_id of %s is not set" % self)
            return

        # floatingips
        neutron = self.neutron_admin_client
        floatingips = neutron.list_floatingips(tenant_id=self.tenant_id)
        if floatingips:
            for floatingip in floatingips['floatingips']:
                logger.info("Deleting floating IP %s from tenant %s", floatingip['id'], self.tenant_id)
                if not dryrun:
                    try:
                        neutron.delete_floatingip(floatingip['id'])
                    except neutron_exceptions.NotFound:
                        logger.debug("Floating IP %s is already gone from tenant %s", floatingip['id'], self.tenant_id)

        # ports
        ports = neutron.list_ports(tenant_id=self.tenant_id)
        if ports:
            for port in ports['ports']:
                logger.info("Deleting port %s from tenant %s", port['id'], self.tenant_id)
                if not dryrun:
                    try:
                        neutron.remove_interface_router(port['device_id'], {'port_id': port['id']})
                    except neutron_exceptions.NotFound:
                        logger.debug("Port %s is already gone from tenant %s", port['id'], self.tenant_id)

        # routers
        routers = neutron.list_routers(tenant_id=self.tenant_id)
        if routers:
            for router in routers['routers']:
                logger.info("Deleting router %s from tenant %s", router['id'], self.tenant_id)
                if not dryrun:
                    try:
                        neutron.delete_router(router['id'])
                    except neutron_exceptions.NotFound:
                        logger.debug("Router %s is already gone from tenant %s", router['id'], self.tenant_id)

        # networks
        networks = neutron.list_networks(tenant_id=self.tenant_id)
        if networks:
            for network in networks['networks']:
                for subnet in network['subnets']:
                    logger.info("Deleting subnetwork %s from tenant %s", subnet, self.tenant_id)
                    if not dryrun:
                        try:
                            neutron.delete_subnet(subnet)
                        except neutron_exceptions.NotFound:
                            logger.info("Subnetwork %s is already gone from tenant %s", subnet, self.tenant_id)

                logger.info("Deleting network %s from tenant %s", network['id'], self.tenant_id)
                if not dryrun:
                    try:
                        neutron.delete_network(network['id'])
                    except neutron_exceptions.NotFound:
                        logger.debug("Network %s is already gone from tenant %s", network['id'], self.tenant_id)

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

    @log_backend_action()
    def cleanup_tenant(self, tenant, dryrun=True):
        if not tenant.backend_id:
            # This method will remove all floating IPs if tenant `backend_id` is not defined.
            raise OpenStackBackendError('Method `cleanup_tenant` should not be called if tenant has no backend_id')
        # floatingips
        neutron = self.neutron_admin_client
        floatingips = neutron.list_floatingips(tenant_id=tenant.backend_id)
        if floatingips:
            for floatingip in floatingips['floatingips']:
                logger.info("Deleting floating IP %s from tenant %s", floatingip['id'], tenant.backend_id)
                if not dryrun:
                    try:
                        neutron.delete_floatingip(floatingip['id'])
                    except (neutron_exceptions.NotFound, keystone_exceptions.ClientException):
                        logger.debug("Floating IP %s is already gone from tenant %s", floatingip['id'], tenant.backend_id)

        # ports
        ports = neutron.list_ports(tenant_id=tenant.backend_id)
        if ports:
            for port in ports['ports']:
                logger.info("Deleting port %s from tenant %s", port['id'], tenant.backend_id)
                if not dryrun:
                    try:
                        neutron.remove_interface_router(port['device_id'], {'port_id': port['id']})
                    except (neutron_exceptions.NotFound, keystone_exceptions.ClientException):
                        logger.debug("Port %s is already gone from tenant %s", port['id'], tenant.backend_id)

        # routers
        routers = neutron.list_routers(tenant_id=tenant.backend_id)
        if routers:
            for router in routers['routers']:
                logger.info("Deleting router %s from tenant %s", router['id'], tenant.backend_id)
                if not dryrun:
                    try:
                        neutron.delete_router(router['id'])
                    except (neutron_exceptions.NotFound, keystone_exceptions.ClientException):
                        logger.debug("Router %s is already gone from tenant %s", router['id'], tenant.backend_id)

        # networks
        networks = neutron.list_networks(tenant_id=tenant.backend_id)
        if networks:
            for network in networks['networks']:
                for subnet in network['subnets']:
                    logger.info("Deleting subnetwork %s from tenant %s", subnet, tenant.backend_id)
                    if not dryrun:
                        try:
                            neutron.delete_subnet(subnet)
                        except (neutron_exceptions.NotFound, keystone_exceptions.ClientException):
                            logger.info("Subnetwork %s is already gone from tenant %s", subnet, tenant.backend_id)

                logger.info("Deleting network %s from tenant %s", network['id'], tenant.backend_id)
                if not dryrun:
                    try:
                        neutron.delete_network(network['id'])
                    except (neutron_exceptions.NotFound, keystone_exceptions.ClientException):
                        logger.debug("Network %s is already gone from tenant %s", network['id'], tenant.backend_id)

        # security groups
        nova = self.nova_client
        sgroups = nova.security_groups.list()
        for sgroup in sgroups:
            logger.info("Deleting security group %s from tenant %s", sgroup.id, tenant.backend_id)
            if not dryrun:
                try:
                    sgroup.delete()
                except (nova_exceptions.ClientException, keystone_exceptions.ClientException):
                    logger.debug("Cannot delete %s from tenant %s", sgroup, tenant.backend_id)

        # servers (instances)
        servers = nova.servers.list()
        for server in servers:
            logger.info("Deleting server %s from tenant %s", server.id, tenant.backend_id)
            if not dryrun:
                server.delete()

        # snapshots
        cinder = self.cinder_client
        snapshots = cinder.volume_snapshots.list()
        for snapshot in snapshots:
            logger.info("Deleting snapshots %s from tenant %s", snapshot.id, tenant.backend_id)
            if not dryrun:
                snapshot.delete()

        # volumes
        volumes = cinder.volumes.list()
        for volume in volumes:
            logger.info("Deleting volume %s from tenant %s", volume.id, tenant.backend_id)
            if not dryrun:
                volume.delete()

        # user
        keystone = self.keystone_client
        try:
            user = keystone.users.find(name=tenant.user_username)
            logger.info('Deleting user %s that was connected to tenant %s', user.name, tenant.backend_id)
            if not dryrun:
                user.delete()
        except keystone_exceptions.ClientException as e:
            logger.error('Cannot delete user %s from tenant %s. Error: %s', tenant.user_username, tenant.backend_id, e)

        # tenant
        keystone = self.keystone_admin_client
        logger.info("Deleting tenant %s", tenant.backend_id)
        if not dryrun:
            try:
                keystone.tenants.delete(tenant.backend_id)
            except keystone_exceptions.ClientException as e:
                six.reraise(OpenStackBackendError, e)

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
                event_logger.openstack_volume.error(
                    "Virtual machine {resource_name} disk extension has failed "
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
                event_logger.openstack_volume.error(
                    "Virtual machine {resource_name} disk extension has failed due to quota limits.",
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
            event_logger.openstack_volume.info(
                "Virtual machine {resource_name} disk has been extended to {volume_size} GB.",
                event_type='resource_volume_extension_succeeded',
                event_context={'resource': instance, 'volume_size': new_core_size_gib},
            )

    def _push_security_group_rules(self, security_group):
        """ Helper method  """
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

    @log_backend_action()
    def create_security_group(self, security_group):
        nova = self.nova_client
        try:
            backend_security_group = nova.security_groups.create(name=security_group.name, description='')
            security_group.backend_id = backend_security_group.id
            security_group.save()
            self._push_security_group_rules(security_group)
        except nova_exceptions.ClientException as e:
            six.reraise(OpenStackBackendError, e)

    @log_backend_action()
    def delete_security_group(self, security_group):
        nova = self.nova_client
        try:
            nova.security_groups.delete(security_group.backend_id)
        except nova_exceptions.ClientException as e:
            six.reraise(OpenStackBackendError, e)

    @log_backend_action()
    def update_security_group(self, security_group):
        nova = self.nova_client
        try:
            backend_security_group = nova.security_groups.find(id=security_group.backend_id)
            if backend_security_group.name != security_group.name:
                nova.security_groups.update(
                    backend_security_group, name=security_group.name, description='')
            self._push_security_group_rules(security_group)
        except nova_exceptions.ClientException as e:
            six.reraise(OpenStackBackendError, e)

    @log_backend_action('create external network for tenant')
    def create_external_network(self, tenant, neutron, network_ip, network_prefix,
                                vlan_id=None, vxlan_id=None, ips_count=None):
        service_project_link = tenant.service_project_link

        if tenant.external_network_id:
            self.connect_tenant_to_external_network(tenant, tenant.external_network_id)

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
        tenant.external_network_id = network_id
        tenant.save(update_fields=['external_network_id'])

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

    def detect_external_network(self, tenant):
        neutron = self.neutron_admin_client
        routers = neutron.list_routers(tenant_id=tenant.backend_id)['routers']
        if bool(routers):
            router = routers[0]
        else:
            logger.warning('Tenant %s (PK: %s) does not have connected routers.', tenant, tenant.pk)
            return

        ext_gw = router.get('external_gateway_info', {})
        if 'network_id' in ext_gw:
            tenant.external_network_id = ext_gw['network_id']
            tenant.save()
            logger.info('Found and set external network with id %s for tenant %s (PK: %s)',
                        ext_gw['network_id'], tenant, tenant.pk)

    @log_backend_action('delete tenant external network')
    def delete_external_network(self, tenant):
        neutron = self.neutron_admin_client

        try:
            floating_ips = neutron.list_floatingips(
                floating_network_id=tenant.external_network_id)['floatingips']

            for ip in floating_ips:
                neutron.delete_floatingip(ip['id'])
                logger.info('Floating IP with id %s has been deleted.', ip['id'])

            ports = neutron.list_ports(network_id=tenant.external_network_id)['ports']
            for port in ports:
                neutron.remove_interface_router(port['device_id'], {'port_id': port['id']})
                logger.info('Port with id %s has been deleted.', port['id'])

            subnets = neutron.list_subnets(network_id=tenant.external_network_id)['subnets']
            for subnet in subnets:
                neutron.delete_subnet(subnet['id'])
                logger.info('Subnet with id %s has been deleted.', subnet['id'])

            neutron.delete_network(tenant.external_network_id)
            logger.info('External network with id %s has been deleted.', tenant.external_network_id)
        except (neutron_exceptions.NeutronClientException,
                keystone_exceptions.ClientException) as e:
            six.reraise(OpenStackBackendError, e)
        else:
            tenant.external_network_id = ''
            tenant.save()

    @log_backend_action('create internal network for tenant')
    def create_internal_network(self, tenant):
        neutron = self.neutron_admin_client

        network_name = '{0}-int-net'.format(tenant.name)
        try:
            network = {
                'name': network_name,
                'tenant_id': self.tenant_id,
            }

            create_response = neutron.create_network({'networks': [network]})
            internal_network_id = create_response['networks'][0]['id']

            subnet_name = 'nc-{0}-subnet01'.format(network_name)

            logger.info('Creating subnet %s for tenant "%s" (PK: %s).', subnet_name, tenant.name, tenant.pk)
            subnet_data = {
                'network_id': internal_network_id,
                'tenant_id': tenant.backend_id,
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
        except (keystone_exceptions.ClientException, neutron_exceptions.NeutronException) as e:
            six.reraise(OpenStackBackendError, e)
        else:
            tenant.internal_network_id = internal_network_id
            tenant.save(update_fields=['internal_network_id'])

    @log_backend_action('allocate floating IP for tenant')
    def allocate_floating_ip_address(self, tenant):
        neutron = self.neutron_admin_client
        try:
            ip_address = neutron.create_floatingip({
                'floatingip': {
                    'floating_network_id': tenant.external_network_id,
                    'tenant_id': tenant.backend_id,
                }
            })['floatingip']
        except neutron_exceptions.NeutronClientException as e:
            six.reraise(OpenStackBackendError, e)
        else:
            tenant.service_project_link.floating_ips.create(
                status='DOWN',
                address=ip_address['floating_ip_address'],
                backend_id=ip_address['id'],
                backend_network_id=ip_address['floating_network_id']
            )

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

    def connect_tenant_to_external_network(self, tenant, external_network_id):
        neutron = self.neutron_admin_client
        logger.debug('About to create external network for tenant "%s" (PK: %s)', tenant.name, tenant.pk)

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

        tenant.external_network_id = external_network_id
        tenant.save()

        logger.info('Router between external network %s and tenant %s was successfully created',
                    external_network_id, tenant.backend_id)

        return external_network_id

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
                raise OpenStackBackendError('Timed out waiting for instance %s to start' % instance.uuid)
        except nova_exceptions.ClientException as e:
            logger.exception('Failed to start instance %s', instance.uuid)
            six.reraise(OpenStackBackendError, e)
        else:
            logger.info('Successfully started instance %s', instance.uuid)

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
                raise OpenStackBackendError('Timed out waiting for instance %s to stop' % instance.uuid)
        except nova_exceptions.ClientException as e:
            logger.exception('Failed to stop instance %s', instance.uuid)
            six.reraise(OpenStackBackendError, e)
        else:
            instance.start_time = None
            instance.save(update_fields=['start_time'])
            logger.info('Successfully stopped instance %s', instance.uuid)

    def restart_instance(self, instance):
        nova = self.nova_client
        logger.debug('About to restart instance %s', instance.uuid)
        try:
            nova.servers.reboot(instance.backend_id)

            if not self._wait_for_instance_status(instance.backend_id, nova, 'ACTIVE', retries=80):
                logger.error('Failed to restart instance %s', instance.uuid)
                raise OpenStackBackendError('Timed out waiting for instance %s to restart' % instance.uuid)
        except nova_exceptions.ClientException as e:
            logger.exception('Failed to restart instance %s', instance.uuid)
            six.reraise(OpenStackBackendError, e)
        else:
            logger.info('Successfully restarted instance %s', instance.uuid)

    def delete_instance(self, instance):
        nova = self.nova_client
        logger.info('About to delete instance %s', instance.uuid)
        try:
            nova.servers.delete(instance.backend_id)

            if not self._wait_for_instance_deletion(instance.backend_id):
                logger.info('Failed to delete instance %s', instance.uuid)
                event_logger.resource.error(
                    'Virtual machine {resource_name} deletion has failed.',
                    event_type='resource_deletion_failed',
                    event_context={'resource': instance})
                raise OpenStackBackendError('Timed out waiting for instance %s to get deleted' % instance.uuid)

        except nova_exceptions.ClientException as e:
            logger.info('Failed to delete instance %s', instance.uuid)
            event_logger.resource.error(
                'Virtual machine {resource_name} deletion has failed.',
                event_type='resource_deletion_failed',
                event_context={'resource': instance})
            six.reraise(OpenStackBackendError, e)
        else:
            logger.info('Successfully deleted instance %s', instance.uuid)
            event_logger.resource.info(
                'Virtual machine {resource_name} has been deleted.',
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

    @log_backend_action()
    def update_tenant(self, tenant):
        keystone = self.keystone_admin_client
        try:
            keystone.tenants.update(tenant.backend_id, name=tenant.name, description=tenant.description)
        except keystone_exceptions.NotFound as e:
            logger.error('Tenant with id %s does not exist', tenant.backend_id)
            six.reraise(OpenStackBackendError, e)

    def create_snapshot(self, volume_id, cinder):
        """
        Create snapshot from volume

        :param: volume id
        :type volume_id: str
        :returns: snapshot id
        :rtype: str
        """
        snapshot = cinder.volume_snapshots.create(
            volume_id, force=True, display_name='snapshot_from_volume_%s' % volume_id)

        logger.debug('About to create temporary snapshot %s' % snapshot.id)

        if not self._wait_for_snapshot_status(snapshot.id, cinder, 'available', 'error'):
            logger.error('Timed out creating snapshot for volume %s', volume_id)
            raise OpenStackBackendError()

        logger.info('Successfully created snapshot %s for volume %s', snapshot.id, volume_id)

        return snapshot
