from __future__ import unicode_literals

import re
import time
import uuid
import logging
import datetime
import calendar
import pkg_resources
import dateutil.parser

from itertools import groupby

from ceilometerclient import client as ceilometer_client
from cinderclient import exceptions as cinder_exceptions
from cinderclient.v1 import client as cinder_client
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.db import transaction
from django.db.models import ProtectedError
from django.utils import dateparse
from django.utils import six
from django.utils import timezone
from django.utils.lru_cache import lru_cache
from glanceclient import exc as glance_exceptions
from glanceclient.v1 import client as glance_client
from keystoneclient import exceptions as keystone_exceptions
from keystoneclient import session as keystone_session
from keystoneclient.auth.identity import v2
from keystoneclient.service_catalog import ServiceCatalog
from keystoneclient.v2_0 import client as keystone_client
from neutronclient.client import exceptions as neutron_exceptions
from neutronclient.v2_0 import client as neutron_client
from novaclient import exceptions as nova_exceptions
from novaclient.v1_1 import client as nova_client

from nodeconductor.core import NodeConductorExtension
from nodeconductor.core.models import SynchronizationStates
from nodeconductor.core.tasks import send_task
from nodeconductor.iaas.log import event_logger
from nodeconductor.iaas import models
from nodeconductor.structure import ServiceBackend, ServiceBackendError, ServiceBackendNotImplemented

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_cinder_version():
    try:
        return pkg_resources.get_distribution('python-cinderclient').parsed_version
    except ValueError:
        return '00000001', '00000001', '00000001', '*final'


@lru_cache(maxsize=1)
def _get_neutron_version():
    try:
        return pkg_resources.get_distribution('python-neutronclient').parsed_version
    except ValueError:
        return '00000002', '00000003', '00000009', '*final'


@lru_cache(maxsize=1)
def _get_nova_version():
    try:
        return pkg_resources.get_distribution('python-novaclient').parsed_version
    except ValueError:
        return '00000002', '00000020', '00000000', '*final'


class CloudBackendError(Exception):
    """
    Base exception for errors occurring during backend communication.
    """
    pass


class CloudBackendInternalError(Exception):
    """
    Exception for errors in helpers.

    This exception will be raised if error happens, but cloud client
    did not raise any exception. It has be caught by public methods.
    """
    pass


class OpenStackClient(object):
    """ Generic OpenStack client. """

    class Session(dict):
        """ Serializable session """

        # There's a temporary need to pass plain text credentials
        # Currently packaged libraries novaclient==2.17.0, neutronclient==2.3.4
        # and cinderclient==1.0.9 don't support token auth.
        # TODO: Switch to token auth on libraries upgrade.
        OPTIONS = ('auth_ref', 'auth_url', 'username', 'password', 'tenant_id', 'tenant_name')

        # Re-create session from credentials every time instead of tracking session key
        # which doesn't work properly with currently packaged libraries anyway
        RECREATE_SESSION = True

        def __init__(self, backend, ks_session=None, **credentials):
            self.backend = backend.__class__()
            self.keystone_session = ks_session

            if not self.keystone_session:
                auth_plugin = v2.Password(**credentials)
                self.keystone_session = keystone_session.Session(auth=auth_plugin, verify=False)

            try:
                # This will eagerly sign in throwing AuthorizationFailure on bad credentials
                self.keystone_session.get_token()
            except (keystone_exceptions.AuthorizationFailure, keystone_exceptions.ConnectionRefused) as e:
                six.reraise(CloudBackendError, e)

            # Preserve session parameters
            # Make sure session has been created first
            if self.RECREATE_SESSION:
                for opt in credentials:
                    self[opt] = credentials[opt]
            else:
                for opt in self.OPTIONS:
                    self[opt] = getattr(self.auth, opt)

        def __getattr__(self, name):
            return getattr(self.keystone_session, name)

        @classmethod
        def factory(cls, backend, session):
            if cls.RECREATE_SESSION:
                return cls(backend, **session)
            else:
                auth_plugin = v2.Token(
                    auth_url=session['auth_url'],
                    token=session['auth_ref']['token']['id'])
                ks_session = keystone_session.Session(auth=auth_plugin)
                return cls(backend, ks_session=ks_session)

        def validate(self):
            expiresat = dateutil.parser.parse(self.auth.auth_ref['token']['expires'])
            if expiresat > timezone.now() + datetime.timedelta(minutes=10):
                return True

            raise CloudBackendError('Invalid OpenStack session')

        def __str__(self):
            return str({k: v if k != 'password' else '***' for k, v in self})

    def create_admin_session(self, keystone_url):
        try:
            credentials = models.OpenStackSettings.objects.get(
                auth_url=keystone_url).get_credentials()
        except models.OpenStackSettings.DoesNotExist as e:
            logger.exception('Failed to find OpenStack credentials for Keystone URL %s', keystone_url)
            six.reraise(CloudBackendError, e)

        self.session = self.Session(self, **credentials)
        return self.session

    def create_tenant_session(self, credentials):
        try:
            self.session = self.Session(self, **credentials)
        except AttributeError as e:
            logger.error('Failed to create OpenStack session.')
            six.reraise(CloudBackendError, e)
        return self.session

    @classmethod
    def recover_session(cls, session):
        """ Recover OpenStack session from serialized object """
        if not session or (not cls.Session.RECREATE_SESSION and not session.get('auth_ref')):
            raise CloudBackendError('Invalid OpenStack session')

        backend = cls()
        return backend.Session.factory(backend, session)

    @classmethod
    def create_keystone_client(cls, session):
        return keystone_client.Client(session=session)

    @classmethod
    def create_nova_client(cls, session):
        if _get_nova_version() >= pkg_resources.parse_version('2.18.0'):
            kwargs = {'session': session.keystone_session}
        else:
            auth_plugin = session.auth
            kwargs = {
                'auth_url': auth_plugin.auth_url,
                'username': auth_plugin.username,
                'api_key': auth_plugin.password,
                'tenant_id': auth_plugin.tenant_id,
                # project_id is tenant_name, id doesn't make sense,
                # pretty usual for OpenStack
                'project_id': auth_plugin.tenant_name,
            }

        return nova_client.Client(**kwargs)

    @classmethod
    def create_neutron_client(cls, session):
        if _get_neutron_version() >= pkg_resources.parse_version('2.3.6'):
            kwargs = {'session': session.keystone_session}
        else:
            auth_plugin = session.auth
            kwargs = {
                'auth_url': auth_plugin.auth_url,
                'username': auth_plugin.username,
                'password': auth_plugin.password,
                'tenant_id': auth_plugin.tenant_id,
                # neutron is different in a sense it is more reasonable to call
                # tenant_name a tenant_name, rather then project_id
                'tenant_name': auth_plugin.tenant_name,
            }

        return neutron_client.Client(**kwargs)

    @classmethod
    def create_cinder_client(cls, session):
        if _get_cinder_version() >= pkg_resources.parse_version('1.1.0'):
            kwargs = {'session': session.keystone_session}
        else:
            auth_plugin = session.auth
            kwargs = {
                'auth_url': auth_plugin.auth_url,
                'username': auth_plugin.username,
                'api_key': auth_plugin.password,
                'tenant_id': auth_plugin.tenant_id,
                # project_id is tenant_name, id doesn't make sense,
                # pretty usual for OpenStack
                'project_id': auth_plugin.tenant_name,
            }

        return cinder_client.Client(**kwargs)

    @classmethod
    def create_glance_client(cls, session):
        catalog = ServiceCatalog.factory(session.auth.auth_ref)
        endpoint = catalog.url_for(service_type='image')

        kwargs = {
            'token': session.get_token(),
            'insecure': True,
            'timeout': 600,
            'ssl_compression': True,
        }

        return glance_client.Client(endpoint, **kwargs)

    @classmethod
    def create_ceilometer_client(cls, session):
        catalog = ServiceCatalog.factory(session.auth.auth_ref)
        endpoint = catalog.url_for(service_type='metering')

        kwargs = {
            'token': lambda: session.get_token(),
            'endpoint': endpoint,
            'insecure': True,
            'timeout': 600,
            'ssl_compression': True,
        }

        return ceilometer_client.Client('2', **kwargs)


class OpenStackBackend(ServiceBackend, OpenStackClient):
    """ NodeConductor interface to OpenStack. """

    MAX_USERNAME_LENGTH = 64

    # For compatibility with ServiceBackend
    def __init__(self, *args, **kwargs):
        pass

    @classmethod
    def create_session(
            cls, keystone_url=None, instance_uuid=None, membership_id=None, check_tenant=True, membership=None,
            **kwargs):
        """ Create OpenStack session using NodeConductor credentials """

        backend = cls()
        if keystone_url:
            return backend.create_admin_session(keystone_url)

        elif instance_uuid or membership or membership_id:
            if instance_uuid:
                instance = models.Instance.objects.get(uuid=instance_uuid)
                membership = instance.cloud_project_membership
            if membership_id:
                membership = models.CloudProjectMembership.objects.get(id=membership_id)
            credentials = {
                'auth_url': membership.cloud.auth_url,
                'username': membership.username,
                'password': membership.password,
            }
            if check_tenant:
                if not membership.tenant_id:
                    raise CloudBackendError("Can't create tenant session, please provide tenant ID")
                credentials['tenant_id'] = membership.tenant_id
            return backend.create_tenant_session(credentials)

        raise CloudBackendError('Missing OpenStack credentials')

    def get_backend_disk_size(self, core_disk_size):
        return core_disk_size / 1024

    def get_backend_ram_size(self, core_ram_size):
        return core_ram_size

    def get_core_disk_size(self, backend_disk_size):
        return backend_disk_size * 1024

    def get_core_ram_size(self, backend_ram_size):
        return backend_ram_size

    # ServiceBackend compatibility methods
    def stop(self, instance):
        instance.schedule_stopping()
        instance.save()
        send_task('iaas', 'stop')(instance.uuid.hex)

    def add_ssh_key(self, public_key, membership):
        return self.push_ssh_public_key(membership, public_key)

    def remove_ssh_key(self, public_key, membership):
        return self.remove_ssh_public_key(membership, public_key)

    def add_user(self, user, membership):
        pass

    def remove_user(self, user, membership):
        pass

    def remove_link(self, membership):
        raise ServiceBackendNotImplemented

    def get_resources_for_import(self):
        raise ServiceBackendNotImplemented

    def get_monthly_cost_estimate(self, instance):
        if not NodeConductorExtension.is_installed('nodeconductor_killbill'):
            raise ServiceBackendNotImplemented

        from nodeconductor_killbill.backend import KillBillBackend, KillBillError
        from nodeconductor.openstack.models import Instance as opInstance

        # XXX: avoid overcharge for resources migrated from IaaS to OpenStack
        if opInstance.objects.filter(uuid=instance.uuid).exists():
            raise ServiceBackendNotImplemented

        try:
            backend = KillBillBackend(instance.customer)
            invoice = backend.get_invoice_estimate(instance)
        except KillBillError as e:
            logger.error("Failed to get cost estimate for instance %s: %s", instance, e)
            six.reraise(ServiceBackendError, e)

        today = datetime.date.today()
        if not invoice['start_date'] <= today <= invoice['end_date']:
            raise ServiceBackendError("Wrong invoice estimate for instance %s: %s" % (instance, invoice))

        # prorata monthly cost estimate based on daily usage cost
        daily_cost = invoice['amount'] / ((today - invoice['start_date']).days + 1)
        monthly_cost = daily_cost * calendar.monthrange(today.year, today.month)[1]

        return monthly_cost

    # CloudAccount related methods
    def push_cloud_account(self, cloud_account):
        # There's nothing to push for OpenStack
        pass

    def pull_cloud_account(self, cloud_account):
        self.pull_flavors(cloud_account)
        self.pull_images(cloud_account)
        self.pull_service_statistics(cloud_account)

    def pull_flavors(self, cloud_account):
        session = self.create_session(keystone_url=cloud_account.auth_url)
        nova = self.create_nova_client(session)

        backend_flavors = nova.flavors.findall(is_public=True)
        backend_flavors = dict(((f.id, f) for f in backend_flavors))

        with transaction.atomic():
            nc_flavors = cloud_account.flavors.all()
            nc_flavors = dict(((f.backend_id, f) for f in nc_flavors))

            backend_ids = set(backend_flavors.keys())
            nc_ids = set(nc_flavors.keys())

            # Remove stale flavors, the ones that are not on backend anymore
            for flavor_id in nc_ids - backend_ids:
                nc_flavor = nc_flavors[flavor_id]
                # Delete the flavor that has instances after NC-178 gets implemented.
                logger.debug('About to delete flavor %s in database', nc_flavor.uuid)
                try:
                    nc_flavor.delete()
                except ProtectedError:
                    logger.info('Skipped deletion of stale flavor %s due to linked instances',
                                nc_flavor.uuid)
                else:
                    logger.info('Deleted stale flavor %s in database', nc_flavor.uuid)

            # Add new flavors, the ones that are not yet in the database
            for flavor_id in backend_ids - nc_ids:
                backend_flavor = backend_flavors[flavor_id]

                nc_flavor = cloud_account.flavors.create(
                    name=backend_flavor.name,
                    cores=backend_flavor.vcpus,
                    ram=self.get_core_ram_size(backend_flavor.ram),
                    disk=self.get_core_disk_size(backend_flavor.disk),
                    backend_id=backend_flavor.id,
                )
                logger.info('Created new flavor %s in database', nc_flavor.uuid)

            # Update matching flavors, the ones that exist in both places
            for flavor_id in nc_ids & backend_ids:
                nc_flavor = nc_flavors[flavor_id]
                backend_flavor = backend_flavors[flavor_id]

                nc_flavor.name = backend_flavor.name
                nc_flavor.cores = backend_flavor.vcpus
                nc_flavor.ram = self.get_core_ram_size(backend_flavor.ram)
                nc_flavor.disk = self.get_core_disk_size(backend_flavor.disk)
                nc_flavor.save()
                logger.debug('Updated existing flavor %s in database', nc_flavor.uuid)

    def pull_images(self, cloud_account):
        session = self.create_session(keystone_url=cloud_account.auth_url)
        glance = self.create_glance_client(session)

        backend_images = dict(
            (image.id, image)
            for image in glance.images.list()
            if not image.deleted
            if image.is_public
        )

        from nodeconductor.iaas.models import TemplateMapping

        with transaction.atomic():
            # Add missing images
            current_image_ids = set()

            # itertools.groupby requires the iterable to be sorted by key
            mapping_queryset = (
                TemplateMapping.objects
                .filter(backend_image_id__in=backend_images.keys())
                .order_by('template__pk')
            )

            mappings_grouped = groupby(mapping_queryset.iterator(), lambda m: m.template.pk)

            for _, mapping_iterator in mappings_grouped:
                # itertools.groupby shares the iterable,
                # store mappings in own list
                mappings = list(mapping_iterator)
                # At least one mapping is guaranteed to be present
                mapping = mappings[0]

                if len(mappings) > 1:
                    logger.error(
                        'Failed to update images for template %s, '
                        'multiple backend images matched: %s',
                        mapping.template, ', '.join(m.backend_image_id for m in mappings),
                    )
                else:
                    backend_image = backend_images[mapping.backend_image_id]
                    # XXX: This might fail in READ REPEATED isolation level,
                    # which is default on MySQL
                    # see https://docs.djangoproject.com/en/1.6/ref/models/querysets/#django.db.models.query.QuerySet.get_or_create
                    image, created = cloud_account.images.get_or_create(
                        template=mapping.template,
                        defaults={'backend_id': mapping.backend_image_id},
                    )

                    if created:
                        logger.info('Created image %s pointing to %s in database', image, image.backend_id)
                    elif (image.backend_id != mapping.backend_image_id or
                            image.min_disk != backend_image.min_disk or
                            image.min_ram != backend_image.min_ram):
                        image.backend_id = mapping.backend_image_id
                        image.min_ram = self.get_core_ram_size(backend_image.min_ram)
                        image.min_disk = self.get_core_disk_size(backend_image.min_disk)
                        image.save()
                        logger.debug('Updated existing image %s to point to %s in database', image, image.backend_id)
                    else:
                        logger.debug('Image %s pointing to %s is already up to date', image, image.backend_id)

                    current_image_ids.add(image.backend_id)

            # Remove stale images,
            # the ones that don't have any template mappings defined for them

            for image in cloud_account.images.exclude(backend_id__in=current_image_ids):
                image.delete()
                logger.info('Removed stale image %s, was pointing to %s in database', image, image.backend_id)

    # CloudProjectMembership related methods
    def push_membership(self, membership):
        try:
            session = self.create_session(keystone_url=membership.cloud.auth_url)

            keystone = self.create_keystone_client(session)
            neutron = self.create_neutron_client(session)

            tenant = self.get_or_create_tenant(membership, keystone)

            username, password = self.get_or_create_user(membership, keystone)

            membership.username = username
            membership.password = password
            membership.tenant_id = tenant.id

            self.ensure_user_is_tenant_admin(username, tenant, keystone)

            self.get_or_create_internal_network(membership, neutron)

            membership.save()

            logger.info('Successfully synchronized CloudProjectMembership with id %s', membership.id)
        except keystone_exceptions.ClientException as e:
            logger.exception('Failed to synchronize CloudProjectMembership with id %s', membership.id)
            six.reraise(CloudBackendError, e)

    def push_ssh_public_key(self, membership, public_key):
        key_name = self.get_key_name(public_key)

        try:
            session = self.create_session(membership=membership)
            nova = self.create_nova_client(session)

            try:
                nova.keypairs.find(fingerprint=public_key.fingerprint)
            except nova_exceptions.NotFound:
                # Fine, it's a new key, let's add it
                logger.info('Propagating ssh public key %s to backend', key_name)
                nova.keypairs.create(name=key_name, public_key=public_key.public_key)
                logger.info('Successfully propagated ssh public key %s to backend', key_name)
            else:
                # Found a key with the same fingerprint, skip adding
                logger.info('Skipped propagating ssh public key %s to backend', key_name)

        except (nova_exceptions.ClientException, keystone_exceptions.ClientException) as e:
            logger.exception('Failed to propagate ssh public key %s to backend', key_name)
            six.reraise(CloudBackendError, e)

    def remove_ssh_public_key(self, membership, public_key):
        try:
            session = self.create_session(membership=membership)
            nova = self.create_nova_client(session)

            # There could be leftovers of key duplicates: remove them all
            keys = nova.keypairs.findall(fingerprint=public_key.fingerprint)
            key_name = self.get_key_name(public_key)
            for key in keys:
                # Remove only keys created with NC
                if key.name == key_name:
                    nova.keypairs.delete(key)

            logger.info('Deleted ssh public key %s from backend', public_key.name)
        except (nova_exceptions.ClientException, keystone_exceptions.ClientException) as e:
            logger.exception('Failed to delete ssh public key %s from backend', public_key.name)
            six.reraise(CloudBackendError, e)

    def push_membership_quotas(self, membership, quotas):
        # mapping to openstack terminology for quotas
        cinder_quota_mapping = {
            'storage': ('gigabytes', self.get_backend_disk_size),
            'volumes': ('volumes', lambda x: x),
            'snapshots': ('snapshots', lambda x: x),
        }
        nova_quota_mapping = {
            'max_instances': ('instances', lambda x: x),    # iaas app quota
            'instances': ('instances', lambda x: x),        # openstack app quota
            'ram': ('ram', self.get_backend_ram_size),
            'vcpu': ('cores', lambda x: x),
        }
        neutron_quota_mapping = {
            'security_group_count': ('security_group', lambda x: x),
            'security_group_rule_count': ('security_group_rule', lambda x: x),
        }

        def extract_backend_quotas(mapping):
            return {
                backend_name: get_backend_value(quotas[name])
                for name, (backend_name, get_backend_value) in mapping.items()
                if name in quotas and quotas[name] is not None
            }

        # split quotas by components
        cinder_quotas = extract_backend_quotas(cinder_quota_mapping)
        nova_quotas = extract_backend_quotas(nova_quota_mapping)
        neutron_quotas = extract_backend_quotas(neutron_quota_mapping)

        if not (cinder_quotas or nova_quotas or neutron_quotas):
            return

        try:
            session = self.create_session(membership=membership)
            try:
                if cinder_quotas:
                    cinder = self.create_cinder_client(session)
                    cinder.quotas.update(membership.tenant_id, **cinder_quotas)
            except cinder_exceptions.ClientException:
                logger.exception('Failed to update membership %s cinder quotas %s', membership, cinder_quotas)

            try:
                if nova_quotas:
                    nova = self.create_nova_client(session)
                    nova.quotas.update(membership.tenant_id, **nova_quotas)
            except nova_exceptions.ClientException:
                logger.exception('Failed to update membership %s nova quotas %s', membership, nova_quotas)

            try:
                if neutron_quotas:
                    neutron = self.create_neutron_client(session)
                    neutron.update_quota(membership.tenant_id, {'quota': neutron_quotas})
            except neutron_exceptions.ClientException:
                logger.exception('Failed to update membership %s neutron quotas %s', membership, neutron_quotas)

        except keystone_exceptions.ClientException as e:
            logger.exception('Failed to update membership %s quotas %s', membership, quotas)
            six.reraise(CloudBackendError, e)

    def push_security_groups(self, membership, is_membership_creation=False):
        logger.debug('About to push security groups for tenant %s', membership.tenant_id)
        try:
            session = self.create_session(membership=membership)
            nova = self.create_nova_client(session)
        except keystone_exceptions.ClientException as e:
            logger.exception('Failed to create nova client')
            six.reraise(CloudBackendError, e)

        nc_security_groups = membership.security_groups.all()
        if not is_membership_creation:
            nc_security_groups = nc_security_groups.filter(state__in=SynchronizationStates.STABLE_STATES)

        try:
            backend_security_groups = dict((str(g.id), g) for g in nova.security_groups.list() if g.name != 'default')
        except nova_exceptions.ClientException as e:
            logger.exception('Failed to get openstack security groups for membership %s', membership.id)
            six.reraise(CloudBackendError, e)

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
                self.delete_security_group(backend_group_id, nova=nova)
            except CloudBackendError, e:
                pass

        # updating unsynchronized security groups
        for nc_group in unsynchronized_groups:
            if nc_group.state in SynchronizationStates.STABLE_STATES:
                nc_group.schedule_syncing()
                nc_group.save()
            send_task(membership.security_groups.model._meta.app_label, 'update_security_group')(nc_group.uuid.hex)

        # creating nonexistent and unsynchronized security groups
        for nc_group in nonexistent_groups:
            if nc_group.state in SynchronizationStates.STABLE_STATES:
                nc_group.schedule_syncing()
                nc_group.save()
            send_task(membership.security_groups.model._meta.app_label, 'create_security_group')(nc_group.uuid.hex)

    def create_security_group(self, security_group, nova):
        logger.debug('About to create security group %s in backend', security_group.uuid)
        try:
            backend_security_group = nova.security_groups.create(name=security_group.name, description='')
            security_group.backend_id = backend_security_group.id
            security_group.save()
            self.push_security_group_rules(security_group, nova)
        except nova_exceptions.ClientException as e:
            logger.exception('Failed to create openstack security group with for %s in backend', security_group.uuid)
            six.reraise(CloudBackendError, e)
        else:
            logger.info('Security group %s successfully created in backend', security_group.uuid)

    def delete_security_group(self, backend_id, nova):
        logger.debug('About to delete security group with id %s in backend', backend_id)
        try:
            nova.security_groups.delete(backend_id)
        except nova_exceptions.ClientException as e:
            logger.exception('Failed to remove openstack security group with id %s in backend', backend_id)
            six.reraise(CloudBackendError, e)
        else:
            logger.info('Security group with id %s successfully deleted in backend', backend_id)

    def update_security_group(self, security_group, nova):
        logger.debug('About to update security group %s in backend', security_group.uuid)
        try:
            backend_security_group = nova.security_groups.find(id=security_group.backend_id)
            if backend_security_group.name != security_group.name:
                nova.security_groups.update(
                    backend_security_group, name=security_group.name, description='')
            self.push_security_group_rules(security_group, nova)
        except nova_exceptions.ClientException as e:
            logger.exception('Failed to update security group %s in backend', security_group.uuid)
            six.reraise(CloudBackendError, e)
        else:
            logger.debug('Security group %s successfully updated in backend', security_group.uuid)

    def pull_security_groups(self, membership):
        # get proper SecurityGroup model class for either iaas or openstack app
        SecurityGroup = membership.security_groups.model

        try:
            session = self.create_session(membership=membership)
            nova = self.create_nova_client(session)
        except keystone_exceptions.ClientException as e:
            logger.exception('Failed to create nova client')
            six.reraise(CloudBackendError, e)

        try:
            backend_security_groups = nova.security_groups.list()
        except nova_exceptions.ClientException as e:
            logger.exception('Failed to get openstack security groups for membership %s', membership.id)
            six.reraise(CloudBackendError, e)

        # list of openstack security groups that do not exist in nc
        nonexistent_groups = []
        # list of openstack security groups that have wrong parameters in in nc
        unsynchronized_groups = []
        # list of nc security groups that do not exist in openstack

        extra_groups = membership.security_groups.exclude(
            backend_id__in=[g.id for g in backend_security_groups],
        )

        with transaction.atomic():
            for backend_group in backend_security_groups:
                try:
                    nc_group = membership.security_groups.get(
                        backend_id=backend_group.id,
                    )
                    if not self._are_security_groups_equal(backend_group, nc_group):
                        unsynchronized_groups.append(backend_group)
                except SecurityGroup.DoesNotExist:
                    nonexistent_groups.append(backend_group)

            # deleting extra security groups
            extra_groups.delete()
            logger.info('Deleted stale security groups in database')

            # synchronizing unsynchronized security groups
            for backend_group in unsynchronized_groups:
                nc_security_group = membership.security_groups.get(
                    backend_id=backend_group.id,
                )
                if backend_group.name != nc_security_group.name:
                    nc_security_group.name = backend_group.name
                    nc_security_group.state = SynchronizationStates.IN_SYNC
                    nc_security_group.save()
                self.pull_security_group_rules(nc_security_group, nova)
            logger.debug('Updated existing security groups in database')

            # creating non-existed security groups
            for backend_group in nonexistent_groups:
                nc_security_group = membership.security_groups.create(
                    backend_id=backend_group.id,
                    name=backend_group.name,
                    state=SynchronizationStates.IN_SYNC
                )
                self.pull_security_group_rules(nc_security_group, nova)
                logger.info('Created new security group %s in database', nc_security_group.uuid)

    def pull_instances(self, membership):
        try:
            session = self.create_session(membership=membership)
            nova = self.create_nova_client(session)
        except keystone_exceptions.ClientException as e:
            logger.exception('Failed to create nova client')
            six.reraise(CloudBackendError, e)
        except cinder_exceptions.ClientException as e:
            logger.exception('Failed to create cinder client')
            six.reraise(CloudBackendError, e)

        # Exclude instances that are booted from images
        backend_instances = nova.servers.findall(image='')
        backend_instances = dict(((f.id, f) for f in backend_instances))

        with transaction.atomic():
            states = (
                models.Instance.States.ONLINE,
                models.Instance.States.OFFLINE,
                models.Instance.States.ERRED)
            nc_instances = models.Instance.objects.filter(
                state__in=states,
                cloud_project_membership=membership,
            )
            nc_instances = dict(((i.backend_id, i) for i in nc_instances))

            backend_ids = set(backend_instances.keys())
            nc_ids = set(nc_instances.keys())

            # Mark stale instances as erred. Can happen if instances are removed from the backend explicitly
            for instance_id in nc_ids - backend_ids:
                nc_instance = nc_instances[instance_id]
                nc_instance.set_erred()
                nc_instance.save()

            # update matching instances
            for instance_id in nc_ids & backend_ids:
                backend_instance = backend_instances[instance_id]
                nc_instance = nc_instances[instance_id]
                nc_instance.state = self._get_instance_state(backend_instance)
                if nc_instance.key_name != backend_instance.key_name:
                    if backend_instance.key_name is None:
                        nc_instance.key_name = ""
                    else:
                        nc_instance.key_name = backend_instance.key_name
                    # note that fingerprint is not present in the request
                    nc_instance.key_fingerprint = ""

                ips = self._get_instance_ips(backend_instance)
                nc_instance.internal_ips = ips.get('internal', '')
                nc_instance.external_ips = ips.get('external', '')

                nc_instance.save()
                # TODO: synchronize also volume sizes

    def pull_resource_quota(self, membership):
        try:
            session = self.create_session(membership=membership)
            nova = self.create_nova_client(session)
            cinder = self.create_cinder_client(session)
            neutron = self.create_neutron_client(session)
        except keystone_exceptions.ClientException as e:
            logger.exception('Failed to create nova client or cinder client')
            six.reraise(CloudBackendError, e)

        logger.debug('About to get quotas for tenant %s', membership.tenant_id)
        try:
            nova_quotas = nova.quotas.get(tenant_id=membership.tenant_id)
            cinder_quotas = cinder.quotas.get(tenant_id=membership.tenant_id)
            neutron_quotas = neutron.show_quota(tenant_id=membership.tenant_id)['quota']
        except (nova_exceptions.ClientException, cinder_exceptions.ClientException) as e:
            logger.exception('Failed to get quotas for tenant %s', membership.tenant_id)
            six.reraise(CloudBackendError, e)
        else:
            logger.info('Successfully got quotas for tenant %s', membership.tenant_id)

        membership.set_quota_limit('ram', self.get_core_ram_size(nova_quotas.ram))
        membership.set_quota_limit('vcpu', nova_quotas.cores)
        membership.set_quota_limit('storage', self.get_core_disk_size(cinder_quotas.gigabytes))
        membership.set_quota_limit('security_group_count', neutron_quotas['security_group'])
        membership.set_quota_limit('security_group_rule_count', neutron_quotas['security_group_rule'])
        membership.set_quota_limit('max_instances', nova_quotas.instances)

    def pull_resource_quota_usage(self, membership):
        try:
            session = self.create_session(membership=membership)
            nova = self.create_nova_client(session)
            cinder = self.create_cinder_client(session)
        except keystone_exceptions.ClientException as e:
            logger.exception('Failed to create nova client or cinder client')
            six.reraise(CloudBackendError, e)

        logger.debug('About to get volumes, snapshots, flavors and instances for tenant %s', membership.tenant_id)
        try:
            volumes = cinder.volumes.list()
            snapshots = cinder.volume_snapshots.list()
            flavors = dict((flavor.id, flavor) for flavor in nova.flavors.list())
            instances = nova.servers.list()
            security_groups = nova.security_groups.list()
        except (nova_exceptions.ClientException, cinder_exceptions.ClientException) as e:
            logger.exception(
                'Failed to get volumes, snapshots, flavors, instances or security_groups for tenant %s',
                membership.tenant_id)
            six.reraise(CloudBackendError, e)
        else:
            logger.info(
                'Successfully got volumes, snapshots, flavors, instances or security_groups for tenant %s',
                membership.tenant_id)

        # ram and vcpu
        instance_flavor_ids = [instance.flavor['id'] for instance in instances]
        ram = 0
        vcpu = 0

        for flavor_id in instance_flavor_ids:
            try:
                flavor = flavors.get(flavor_id, nova.flavors.get(flavor_id))
            except nova_exceptions.NotFound:
                logger.warning('Cannot find flavor with id %s', flavor_id)
                continue

            ram += self.get_core_ram_size(getattr(flavor, 'ram', 0))
            vcpu += getattr(flavor, 'vcpus', 0)

        membership.set_quota_usage('ram', ram)
        membership.set_quota_usage('vcpu', vcpu)
        membership.set_quota_usage('instances', len(instances), fail_silently=True)
        membership.set_quota_usage('max_instances', len(instances), fail_silently=True)
        membership.set_quota_usage('storage', sum([self.get_core_disk_size(v.size) for v in volumes + snapshots]))
        membership.set_quota_usage('security_group_count', len(security_groups))
        membership.set_quota_usage('security_group_rule_count', len(sum([sg.rules for sg in security_groups], [])))

    def pull_floating_ips(self, membership):
        logger.debug('Pulling floating ips for membership %s', membership.id)
        try:
            session = self.create_session(membership=membership)
            neutron = self.create_neutron_client(session)
        except keystone_exceptions.ClientException as e:
            logger.exception('Failed to create neutron client')
            six.reraise(CloudBackendError, e)

        try:
            backend_floating_ips = {
                ip['id']: ip
                for ip in self.get_floating_ips(membership.tenant_id, neutron)
                if ip.get('floating_ip_address') and ip.get('status')
            }
        except neutron_exceptions.ClientException as e:
            logger.exception('Failed to get a list of floating IPs')
            six.reraise(CloudBackendError, e)

        nc_floating_ips = dict(
            (ip.backend_id, ip) for ip in membership.floating_ips.all())

        backend_ids = set(backend_floating_ips.keys())
        nc_ids = set(nc_floating_ips.keys())

        with transaction.atomic():

            for ip_id in nc_ids - backend_ids:
                ip = nc_floating_ips[ip_id]
                ip.delete()
                logger.info('Deleted stale floating IP port %s in database', ip.uuid)

            for ip_id in backend_ids - nc_ids:
                ip = backend_floating_ips[ip_id]
                created_ip = membership.floating_ips.create(
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

    # Statistics methods
    def get_resource_stats(self, auth_url):
        logger.debug('About to get statistics for auth_url: %s', auth_url)
        try:
            session = self.create_session(keystone_url=auth_url)
            nova = self.create_nova_client(session)
            stats = self.get_hypervisors_statistics(nova)

            # XXX a temporary workaround for https://bugs.launchpad.net/nova/+bug/1333520
            if 'vcpus' in stats:
                nc_settings = getattr(settings, 'NODECONDUCTOR', {})
                openstacks = nc_settings.get('OPENSTACK_OVERCOMMIT', ())
                try:
                    openstack = next(o for o in openstacks if o['auth_url'] == auth_url)
                    cpu_overcommit_ratio = openstack.get('cpu_overcommit_ratio', 1)
                except StopIteration as e:
                    logger.debug('Failed to find OpenStack overcommit values for Keystone URL %s', auth_url)
                    cpu_overcommit_ratio = 1
                stats['vcpus'] = stats['vcpus'] * cpu_overcommit_ratio

        except (nova_exceptions.ClientException, keystone_exceptions.ClientException) as e:
            logger.exception('Failed to get statistics for auth_url: %s', auth_url)
            six.reraise(CloudBackendError, e)
        else:
            logger.debug('Successfully for auth_url: %s was successfully taken', auth_url)
        return stats

    def pull_service_statistics(self, cloud_account, service_stats=None):
        if not service_stats:
            service_stats = self.get_resource_stats(cloud_account.auth_url)

        cloud_stats = dict((s.key, s) for s in cloud_account.stats.all())
        for key, val in service_stats.items():
            stats = cloud_stats.pop(key, None)
            if stats:
                stats.value = val
                stats.save()
            else:
                cloud_account.stats.create(key=key, value=val)

        if cloud_stats:
            cloud_account.stats.delete(key__in=cloud_stats.keys())

        return service_stats

    # Instance related methods
    def provision_instance(self, instance, backend_flavor_id, system_volume_id=None, data_volume_id=None):
        logger.info('About to boot instance %s', instance.uuid)
        try:
            membership = instance.cloud_project_membership

            image = membership.cloud.images.get(
                template=instance.template,
            )

            session = self.create_session(membership=membership)

            nova = self.create_nova_client(session)
            cinder = self.create_cinder_client(session)
            neutron = self.create_neutron_client(session)

            # verify if the internal network to connect to exists
            try:
                neutron.show_network(membership.internal_network_id)
            except neutron_exceptions.NeutronClientException:
                logger.exception('Internal network with id of %s was not found',
                                 membership.internal_network_id)
                raise CloudBackendError('Unable to find network to attach instance to')

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
                        # TODO: warning as we trust that fingerprint+name combo is unique. Potentially reconsider.
                        logger.warning('Found %d public keys with fingerprint "%s", expected exactly one.' +
                                       'Taking the first one',
                                       matching_keys_count, instance.key_fingerprint)
                    backend_public_key = matching_keys[0]
                elif matching_keys_count == 0:
                    logger.error('Found no public keys with fingerprint "%s", expected exactly one',
                                 instance.key_fingerprint)
                    # It is possible to fix this situation with OpenStack admin account. So not failing here.
                    # Error log is expected to be addressed.
                    # TODO: consider failing provisioning/putting this check into serializer/pre-save.
                    # reset failed key name/fingerprint
                    instance.key_name = ''  # has to be an empty string, if None will fail on MySQL backend
                    instance.key_fingerprint = ''
                    backend_public_key = None
                else:
                    backend_public_key = matching_keys[0]
            else:
                backend_public_key = None

            backend_flavor = nova.flavors.get(backend_flavor_id)

            if not system_volume_id:
                system_volume_name = '{0}-system'.format(instance.name)
                logger.info('Creating volume %s for instance %s', system_volume_name, instance.uuid)
                # TODO: need to update system_volume_size as well for the data to be precise
                size = self.get_backend_disk_size(instance.system_volume_size)
                system_volume = cinder.volumes.create(
                    size=size,
                    display_name=system_volume_name,
                    display_description='',
                    imageRef=image.backend_id,
                )
                system_volume_id = system_volume.id

            if not data_volume_id:
                data_volume_name = '{0}-data'.format(instance.name)
                logger.info('Creating volume %s for instance %s', data_volume_name, instance.uuid)
                # TODO: need to update data_volume_size as well for the data to be precise
                size = self.get_backend_disk_size(instance.data_volume_size)
                data_volume = cinder.volumes.create(
                    size=size,
                    display_name=data_volume_name,
                    display_description='',
                )
                data_volume_id = data_volume.id

            if not self._wait_for_volume_status(system_volume_id, cinder, 'available', 'error'):
                logger.error(
                    'Failed to boot instance %s: timed out waiting for system volume %s to become available',
                    instance.uuid, system_volume_id,
                )
                raise CloudBackendError('Timed out waiting for instance %s to boot' % instance.uuid)

            if not self._wait_for_volume_status(data_volume_id, cinder, 'available', 'error'):
                logger.error(
                    'Failed to boot instance %s: timed out waiting for data volume %s to become available',
                    instance.uuid, data_volume_id,
                )
                raise CloudBackendError('Timed out waiting for instance %s to boot' % instance.uuid)

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
                    # This should have worked by creating an empty volume.
                    # But, as always, OpenStack doesn't work as advertised:
                    # see https://bugs.launchpad.net/nova/+bug/1347499
                    # equivalent nova boot options would be
                    # --block-device source=blank,dest=volume,size=10,type=disk
                    # {
                    # 'destination_type': 'blank',
                    #     'device_type': 'disk',
                    #     'source_type': 'image',
                    #     'uuid': backend_image.id,
                    #     'volume_size': 10,
                    #     'shutdown': 'remove',
                    # },
                ],
                nics=[
                    {'net-id': membership.internal_network_id}
                ],
                key_name=backend_public_key.name if backend_public_key is not None else None,
                security_groups=security_group_ids,
            )
            if membership.availability_zone:
                server_create_parameters['availability_zone'] = membership.availability_zone
            if instance.user_data:
                server_create_parameters['userdata'] = instance.user_data

            server = nova.servers.create(**server_create_parameters)

            instance.backend_id = server.id
            instance.system_volume_id = system_volume_id
            instance.data_volume_id = data_volume_id
            instance.save()

            if not self._wait_for_instance_status(server.id, nova, 'ACTIVE'):
                logger.error(
                    'Failed to boot instance %s: timed out while waiting for instance to become online',
                    instance.uuid,
                )
                raise CloudBackendError('Timed out waiting for instance %s to boot' % instance.uuid)
            instance.start_time = timezone.now()
            instance.save()

            logger.debug('About to infer internal ip addresses of instance %s', instance.uuid)
            try:
                server = nova.servers.get(server.id)
                fixed_address = server.addresses.values()[0][0]['addr']
            except (nova_exceptions.ClientException, KeyError, IndexError):
                logger.exception('Failed to infer internal ip addresses of instance %s',
                                 instance.uuid)
            else:
                instance.internal_ips = fixed_address
                instance.save()
                logger.info('Successfully inferred internal ip addresses of instance %s',
                            instance.uuid)

            # Floating ips initialization
            self.push_floating_ip_to_instance(server, instance, nova)

        except (glance_exceptions.ClientException,
                cinder_exceptions.ClientException,
                nova_exceptions.ClientException,
                neutron_exceptions.NeutronClientException) as e:
            logger.exception('Failed to boot instance %s', instance.uuid)

            event_logger.instance.error(
                'Virtual machine {instance_name} creation has failed.',
                event_type='iaas_instance_creation_failed',
                event_context={'instance': instance})
            six.reraise(CloudBackendError, e)
        else:
            logger.info('Successfully booted instance %s', instance.uuid)

            event_logger.instance.info(
                'Virtual machine {instance_name} has been created.',
                event_type='iaas_instance_creation_succeeded',
                event_context={'instance': instance})

            event_logger.instance.info(
                'Virtual machine {instance_name} has been started.',
                event_type='iaas_instance_start_succeeded',
                event_context={'instance': instance})

            licenses = instance.instance_licenses.all()
            event_logger.instance_licenses.info(
                'Licenses added to VM with name {instance_name}.',
                event_type='iaas_instance_licenses_added',
                event_context={
                    'instance': instance,
                    'licenses_types': [l.template_license.license_type for l in licenses],
                    'licenses_services_types': [l.template_license.service_type for l in licenses],
                }
            )

    def start_instance(self, instance):
        logger.debug('About to start instance %s', instance.uuid)

        try:
            membership = instance.cloud_project_membership

            session = self.create_session(membership=membership)

            nova = self.create_nova_client(session)

            backend_instance = nova.servers.find(id=instance.backend_id)
            backend_instance_state = self._get_instance_state(backend_instance)

            if backend_instance_state == models.Instance.States.ONLINE:
                logger.warning('Instance %s is already started', instance.uuid)
                # TODO: throws exception for some reason, investigation pending
                # instance.start_time = self._get_instance_start_time(backend_instance)
                instance.start_time = timezone.now()
                instance.save()
                logger.info('Successfully started instance %s', instance.uuid)
                event_logger.instance.info(
                    'Virtual machine {instance_name} has been started.',
                    event_type='iaas_instance_start_succeeded',
                    event_context={'instance': instance})
                return

            nova.servers.start(instance.backend_id)

            if not self._wait_for_instance_status(instance.backend_id, nova, 'ACTIVE'):
                logger.error('Failed to start instance %s', instance.uuid)
                event_logger.instance.error(
                    'Virtual machine {instance_name} start has failed.',
                    event_type='iaas_instance_start_failed',
                    event_context={'instance': instance})
                raise CloudBackendError('Timed out waiting for instance %s to start' % instance.uuid)
        except nova_exceptions.ClientException as e:
            logger.exception('Failed to start instance %s', instance.uuid)
            event_logger.instance.error(
                'Virtual machine {instance_name} start has failed.',
                event_type='iaas_instance_start_failed',
                event_context={'instance': instance})
            six.reraise(CloudBackendError, e)
        else:
            instance.start_time = timezone.now()
            instance.save()

            logger.info('Successfully started instance %s', instance.uuid)
            event_logger.instance.info(
                'Virtual machine {instance_name} has been started.',
                event_type='iaas_instance_start_succeeded',
                event_context={'instance': instance})

    def stop_instance(self, instance):
        logger.debug('About to stop instance %s', instance.uuid)

        try:
            membership = instance.cloud_project_membership

            session = self.create_session(membership=membership)

            nova = self.create_nova_client(session)

            backend_instance = nova.servers.find(id=instance.backend_id)
            backend_instance_state = self._get_instance_state(backend_instance)

            if backend_instance_state == models.Instance.States.OFFLINE:
                logger.warning('Instance %s is already stopped', instance.uuid)
                instance.start_time = None
                instance.save()
                logger.info('Successfully stopped instance %s', instance.uuid)
                event_logger.instance.info(
                    'Virtual machine {instance_name} has been stopped.',
                    event_type='iaas_instance_stop_succeeded',
                    event_context={'instance': instance})
                return

            nova.servers.stop(instance.backend_id)

            if not self._wait_for_instance_status(instance.backend_id, nova, 'SHUTOFF'):
                logger.error('Failed to stop instance %s', instance.uuid)
                event_logger.instance.error(
                    'Virtual machine {instance_name} stop has failed.',
                    event_type='iaas_instance_stop_failed',
                    event_context={'instance': instance})
                raise CloudBackendError('Timed out waiting for instance %s to stop' % instance.uuid)
        except nova_exceptions.ClientException as e:
            logger.exception('Failed to stop instance %s', instance.uuid)
            event_logger.instance.error(
                'Virtual machine {instance_name} stop has failed.',
                event_type='iaas_instance_stop_failed',
                event_context={'instance': instance})
            six.reraise(CloudBackendError, e)
        else:
            instance.start_time = None
            instance.save()
            logger.info('Successfully stopped instance %s', instance.uuid)
            event_logger.instance.info(
                'Virtual machine {instance_name} has been stopped.',
                event_type='iaas_instance_stop_succeeded',
                event_context={'instance': instance})

    def restart_instance(self, instance):
        logger.debug('About to restart instance %s', instance.uuid)
        try:
            membership = instance.cloud_project_membership

            session = self.create_session(membership=membership)

            nova = self.create_nova_client(session)
            nova.servers.reboot(instance.backend_id)

            if not self._wait_for_instance_status(instance.backend_id, nova, 'ACTIVE', retries=80):
                logger.error('Failed to restart instance %s', instance.uuid)
                event_logger.instance.error(
                    'Virtual machine {instance_name} restart has failed.',
                    event_type='iaas_instance_restart_failed',
                    event_context={'instance': instance})
                raise CloudBackendError('Timed out waiting for instance %s to restart' % instance.uuid)
        except nova_exceptions.ClientException as e:
            logger.exception('Failed to restart instance %s', instance.uuid)
            event_logger.instance.error(
                'Virtual machine {instance_name} restart has failed.',
                event_type='iaas_instance_restart_failed',
                event_context={'instance': instance})
            six.reraise(CloudBackendError, e)
        else:
            logger.info('Successfully restarted instance %s', instance.uuid)
            event_logger.instance.info(
                'Virtual machine {instance_name} has been restarted.',
                event_type='iaas_instance_restart_succeeded',
                event_context={'instance': instance})

    def delete_instance(self, instance):
        logger.info('About to delete instance %s', instance.uuid)
        try:
            membership = instance.cloud_project_membership

            session = self.create_session(membership=membership)

            nova = self.create_nova_client(session)
            nova.servers.delete(instance.backend_id)

            if not self._wait_for_instance_deletion(instance.backend_id, nova):
                logger.info('Failed to delete instance %s', instance.uuid)
                event_logger.instance.error(
                    'Virtual machine {instance_name} deletion has failed.',
                    event_type='iaas_instance_deletion_failed',
                    event_context={'instance': instance})
                raise CloudBackendError('Timed out waiting for instance %s to get deleted' % instance.uuid)
            else:
                self.release_floating_ip_from_instance(instance)

        except nova_exceptions.ClientException as e:
            logger.info('Failed to delete instance %s', instance.uuid)
            event_logger.instance.error(
                'Virtual machine {instance_name} deletion has failed.',
                event_type='iaas_instance_deletion_failed',
                event_context={'instance': instance})
            six.reraise(CloudBackendError, e)
        else:
            logger.info('Successfully deleted instance %s', instance.uuid)
            event_logger.instance.info(
                'Virtual machine {instance_name} has been deleted.',
                event_type='iaas_instance_deletion_succeeded',
                event_context={'instance': instance})

    def import_instance(self, membership, instance_id, template_id=None):
        try:
            session = self.create_session(membership=membership)
            nova = self.create_nova_client(session)
            cinder = self.create_cinder_client(session)
        except keystone_exceptions.ClientException as e:
            logger.exception('Failed to create nova client')
            six.reraise(CloudBackendError, e)
        except cinder_exceptions.ClientException as e:
            logger.exception('Failed to create cinder client')
            six.reraise(CloudBackendError, e)

        # Exclude instances that are booted from images
        try:
            backend_instance = nova.servers.get(instance_id)
        except nova_exceptions.NotFound:
            logger.exception('Requested instance with UUID %s was not found', instance_id)
            return

        with transaction.atomic():
            try:
                system_volume, data_volume = self._get_instance_volumes(nova, cinder, instance_id)
                if template_id:
                    try:
                        template = models.Template.objects.get(uuid=template_id)
                    except models.Template.DoesNotExist:
                        logger.exception('Failed to load provided template information for uuid %s', template_id)
                        six.reraise(CloudBackendError, e)
                else:
                    # try to devise from volume image metadata
                    template = self._get_instance_template(system_volume, membership, instance_id)
                cores, ram, flavor_name = self._get_flavor_info(nova, backend_instance)
                state = self._get_instance_state(backend_instance)
            except LookupError as e:
                logger.exception('Failed to lookup instance %s information', instance_id)
                six.reraise(CloudBackendError, e)

            # check if all instance security groups exist in nc
            nc_security_groups = []
            for sg in backend_instance.security_groups:
                try:
                    nc_security_groups.append(
                        models.SecurityGroup.objects.get(name=sg['name'], cloud_project_membership=membership))
                except models.SecurityGroup.DoesNotExist as e:
                    logger.exception('Failed to lookup instance %s information', instance_id)
                    six.reraise(CloudBackendError, e)

            nc_instance = models.Instance(
                name=backend_instance.name or '',
                template=template,
                agreed_sla=template.sla_level,

                flavor_name=flavor_name,
                cores=cores,
                ram=ram,

                key_name=backend_instance.key_name or '',

                system_volume_id=system_volume.id,
                system_volume_size=self.get_core_disk_size(system_volume.size),
                data_volume_id=data_volume.id,
                data_volume_size=self.get_core_disk_size(data_volume.size),

                state=state,

                start_time=self._get_instance_start_time(backend_instance),

                cloud_project_membership=membership,
                backend_id=backend_instance.id,
            )

            ips = self._get_instance_ips(backend_instance)
            if 'internal' in ips:
                nc_instance.internal_ips = ips['internal']
            if 'external' in ips:
                nc_instance.external_ips = ips['external']

            nc_instance.save()

            # instance security groups
            for nc_sg in nc_security_groups:
                models.InstanceSecurityGroup.objects.create(
                    instance=nc_instance,
                    security_group=nc_sg,
                )

            event_logger.instance_import.info(
                'Virtual machine {instance_id} has been imported.',
                event_type='iaas_instance_import_succeeded',
                event_context={'instance_id': instance_id})
            logger.info('Created new instance %s in database', nc_instance.uuid)

            return nc_instance

    # XXX: This method is not used now
    def backup_instance(self, instance):
        logger.debug('About to create instance %s backup', instance.uuid)
        try:
            membership = instance.cloud_project_membership

            session = self.create_session(membership=membership)

            nova = self.create_nova_client(session)
            cinder = self.create_cinder_client(session)

            backups = []
            attached_volumes = self.get_attached_volumes(instance.backend_id, nova)

            for volume in attached_volumes:
                # TODO: Consider using context managers to avoid having resource remnants
                snapshot = self.create_snapshot(volume.id, cinder).id
                temporary_volume = self.create_volume_from_snapshot(snapshot, cinder)
                backup = self.create_volume_backup(temporary_volume, volume.device, cinder)
                backups.append(backup)
                self.delete_volume(temporary_volume, cinder)
                self.delete_snapshot(snapshot, cinder)
        except (nova_exceptions.ClientException, cinder_exceptions.ClientException,
                keystone_exceptions.ClientException, CloudBackendInternalError) as e:
            logger.exception('Failed to create backup for instance %s', instance.uuid)
            six.reraise(CloudBackendError, e)
        else:
            logger.info('Successfully created backup for instance %s', instance.uuid)
        return backups

    def clone_volumes(self, membership, volume_ids, prefix='Cloned volume'):
        logger.debug('About to copy volumes %s', ', '.join(volume_ids))
        try:
            session = self.create_session(membership=membership)
            cinder = self.create_cinder_client(session)

            cloned_volume_ids = []
            for volume_id in volume_ids:
                # create a temporary snapshot
                snapshot = self.create_snapshot(volume_id, cinder)
                membership.add_quota_usage('storage', self.get_core_disk_size(snapshot.size))

                # volume
                promoted_volume_id = self.create_volume_from_snapshot(snapshot.id, cinder, prefix=prefix)
                cloned_volume_ids.append(promoted_volume_id)
                # volume size should be equal to a snapshot size
                membership.add_quota_usage('storage', self.get_core_disk_size(snapshot.size))

                # clean-up created snapshot
                self.delete_snapshot(snapshot.id, cinder)
                if not self._wait_for_snapshot_deletion(snapshot.id, cinder):
                    logger.exception('Timed out waiting for snapshot %s to become available', snapshot.id)
                    raise CloudBackendInternalError()

                membership.add_quota_usage('storage', -self.get_core_disk_size(snapshot.size))

        except (cinder_exceptions.ClientException,
                keystone_exceptions.ClientException, CloudBackendInternalError) as e:
            logger.exception('Failed to clone volumes %s', ', '.join(volume_ids))
            six.reraise(CloudBackendError, e)
        else:
            logger.info('Successfully cloned volumes %s', ', '.join(volume_ids))
        return cloned_volume_ids

    def create_snapshots(self, membership, volume_ids, prefix='Cloned volume'):
        logger.debug('About to snapshot volumes %s', ', '.join(volume_ids))
        try:
            session = self.create_session(membership=membership)
            cinder = self.create_cinder_client(session)

            snapshot_ids = []
            for volume_id in volume_ids:
                # create a temporary snapshot
                snapshot = self.create_snapshot(volume_id, cinder)
                membership.add_quota_usage('storage', self.get_core_disk_size(snapshot.size))
                snapshot_ids.append(snapshot.id)

        except (cinder_exceptions.ClientException,
                keystone_exceptions.ClientException, CloudBackendInternalError) as e:
            logger.exception('Failed to snapshot volumes %s', ', '.join(volume_ids))
            six.reraise(CloudBackendError, e)
        else:
            logger.info('Successfully created snapshots %s for volumes.', ', '.join(snapshot_ids))
        return snapshot_ids

    def promote_snapshots_to_volumes(self, membership, snapshot_ids, prefix='Promoted volume'):
        logger.debug('About to promote snapshots %s', ', '.join(snapshot_ids))
        try:
            session = self.create_session(membership=membership)
            cinder = self.create_cinder_client(session)

            promoted_volume_ids = []
            for snapshot_id in snapshot_ids:
                # volume
                snapshot = cinder.volume_snapshots.get(snapshot_id)
                promoted_volume_id = self.create_volume_from_snapshot(snapshot_id, cinder, prefix=prefix)
                promoted_volume_ids.append(promoted_volume_id)
                # volume size should be equal to a snapshot size
                membership.add_quota_usage('storage', self.get_core_disk_size(snapshot.size))

        except (cinder_exceptions.ClientException,
                keystone_exceptions.ClientException, CloudBackendInternalError) as e:
            logger.exception('Failed to promote snapshots %s', ', '.join(snapshot_ids))
            six.reraise(CloudBackendError, e)
        else:
            logger.info('Successfully promoted volumes %s', ', '.join(promoted_volume_ids))
        return promoted_volume_ids

    def delete_volumes(self, membership, volume_ids):
        logger.debug('About to delete volumes %s ', ', '.join(volume_ids))
        try:
            session = self.create_session(membership=membership)
            cinder = self.create_cinder_client(session)

            for volume_id in volume_ids:
                # volume
                size = cinder.volumes.get(volume_id).size
                self.delete_volume(volume_id, cinder)

                if self._wait_for_volume_deletion(volume_id, cinder):
                    membership.add_quota_usage('storage', -self.get_core_disk_size(size))
                else:
                    logger.exception('Failed to delete volume %s', volume_id)

        except (cinder_exceptions.ClientException,
                keystone_exceptions.ClientException, CloudBackendInternalError) as e:
            logger.exception(
                'Failed to delete volumes %s', ', '.join(volume_ids))
            six.reraise(CloudBackendError, e)
        else:
            logger.info(
                'Successfully deleted volumes %s', ', '.join(volume_ids))

    def delete_snapshots(self, membership, snapshot_ids):
        logger.debug('About to delete volumes %s ', ', '.join(snapshot_ids))
        try:
            session = self.create_session(membership=membership)
            cinder = self.create_cinder_client(session)

            for snapshot_id in snapshot_ids:
                # volume
                size = cinder.volume_snapshots.get(snapshot_id).size
                self.delete_snapshot(snapshot_id, cinder)

                if self._wait_for_snapshot_deletion(snapshot_id, cinder):
                    membership.add_quota_usage('storage', -self.get_core_disk_size(size))
                else:
                    logger.exception('Failed to delete snapshot %s', snapshot_id)

        except (cinder_exceptions.ClientException,
                keystone_exceptions.ClientException, CloudBackendInternalError) as e:
            logger.exception(
                'Failed to delete snapshots %s', ', '.join(snapshot_ids))
            six.reraise(CloudBackendError, e)
        else:
            logger.info(
                'Successfully deleted snapshots %s', ', '.join(snapshot_ids))

    def push_instance_security_groups(self, instance):
        # get proper SecurityGroup model class for either iaas or openstack app
        SecurityGroup = instance.security_groups.model.security_group.get_queryset().model

        try:
            membership = instance.cloud_project_membership

            session = self.create_session(membership=membership)
            nova = self.create_nova_client(session)

            server_id = instance.backend_id

            backend_groups = nova.servers.list_security_group(server_id)
            backend_ids = set(g.id for g in backend_groups)

            nc_ids = set(
                SecurityGroup.objects
                .filter(instance_groups__instance__backend_id=server_id)
                .exclude(backend_id='')
                .values_list('backend_id', flat=True)
            )

            # remove stale groups
            for group_id in backend_ids - nc_ids:
                try:
                    nova.servers.remove_security_group(server_id, group_id)
                except nova_exceptions.ClientException:
                    logger.exception('Failed remove security group %s from instance %s',
                                     group_id, server_id)
                else:
                    logger.info('Removed security group %s from instance %s',
                                group_id, server_id)

            # add missing groups
            for group_id in nc_ids - backend_ids:
                try:
                    nova.servers.add_security_group(server_id, group_id)
                except nova_exceptions.ClientException:
                    logger.exception('Failed add security group %s to instance %s',
                                     group_id, server_id)
                else:
                    logger.info('Added security group %s to instance %s',
                                group_id, server_id)

        except keystone_exceptions.ClientException as e:
            logger.exception('Failed to create nova client')
            six.reraise(CloudBackendError, e)

    def extend_disk(self, instance):
        try:
            membership = instance.cloud_project_membership

            session = self.create_session(membership=membership)

            nova = self.create_nova_client(session)
            cinder = self.create_cinder_client(session)

            server_id = instance.backend_id

            volume = cinder.volumes.get(instance.data_volume_id)

            new_core_size = instance.data_volume_size
            old_core_size = self.get_core_disk_size(volume.size)
            new_backend_size = self.get_backend_disk_size(new_core_size)

            new_core_size_gib = int(round(new_core_size / 1024.0))

            if old_core_size == new_core_size:
                logger.info('Not extending volume %s: it is already of size %d MiB',
                            volume.id, new_core_size)
                return
            elif old_core_size > new_core_size:
                logger.warning('Not extending volume %s: desired size %d MiB is less then current size %d MiB',
                               volume.id, new_core_size, old_core_size)
                event_logger.instance_volume.error(
                    "Virtual machine {instance_name} disk extension has failed "
                    "due to new size being less than old size.",
                    event_type='iaas_instance_volume_extension_failed',
                    event_context={'instance': instance}
                )
                return

            self._detach_volume(nova, cinder, server_id, volume.id, instance.uuid)

            try:
                self._extend_volume(cinder, volume, new_backend_size)
                storage_delta = new_core_size - old_core_size
                membership.add_quota_usage('storage', storage_delta)
            except cinder_exceptions.OverLimit:
                logger.warning(
                    'Failed to extend volume: exceeded quota limit while trying to extend volume %s',
                    volume.id,
                )
                event_logger.instance_volume.error(
                    "Virtual machine {instance_name} disk extension has failed due to quota limits.",
                    event_type='iaas_instance_volume_extension_failed',
                    event_context={'instance': instance},
                )
                # Reset instance.data_volume_size back so that model reflects actual state
                instance.data_volume_size = old_core_size
                instance.save()

                # Omit logging success
                raise
            finally:
                self._attach_volume(nova, cinder, server_id, volume.id, instance.uuid)
        except cinder_exceptions.OverLimit:
            # Omit logging success
            pass
        except (nova_exceptions.ClientException, cinder_exceptions.ClientException) as e:
            logger.exception('Failed to extend disk of an instance %s', instance.uuid)
            six.reraise(CloudBackendError, e)
        else:
            logger.info('Successfully extended disk of an instance %s', instance.uuid)
            event_logger.instance_volume.info(
                "Virtual machine {instance_name} disk has been extended to {volume_size} GB.",
                event_type='iaas_instance_volume_extension_succeeded',
                event_context={'instance': instance, 'volume_size': new_core_size_gib},
            )

    def update_flavor(self, instance, flavor):
        try:
            membership = instance.cloud_project_membership

            session = self.create_session(membership=membership)

            nova = self.create_nova_client(session)
            server_id = instance.backend_id
            flavor_id = flavor.backend_id

            nova.servers.resize(server_id, flavor_id, 'MANUAL')

            if not self._wait_for_instance_status(server_id, nova, 'VERIFY_RESIZE'):
                logger.error(
                    'Failed to change flavor: timed out waiting instance %s to begin resizing',
                    instance.uuid,
                )
                raise CloudBackendError(
                    'Timed out waiting instance %s to begin resizing' % instance.uuid,
                )

            nova.servers.confirm_resize(server_id)

            if not self._wait_for_instance_status(server_id, nova, 'SHUTOFF'):
                logger.error(
                    'Failed to change flavor: timed out waiting instance %s to confirm resizing',
                    instance.uuid,
                )
                raise CloudBackendError(
                    'Timed out waiting instance %s to confirm resizing' % instance.uuid,
                )
        except (nova_exceptions.ClientException, cinder_exceptions.ClientException) as e:
            logger.exception('Failed to change flavor of an instance %s', instance.uuid)
            event_logger.instance_flavor.error(
                'Virtual machine {instance_name} flavor change has failed.',
                event_type='iaas_instance_flavor_change_failed',
                event_context={'instance': instance, 'flavor': flavor}
            )
            six.reraise(CloudBackendError, e)
        except CloudBackendError:
            event_logger.instance_flavor.error(
                'Virtual machine {instance_name} flavor change has failed.',
                event_type='iaas_instance_flavor_change_failed',
                event_context={'instance': instance, 'flavor': flavor}
            )
            raise
        else:
            logger.info('Successfully changed flavor of an instance %s', instance.uuid)
            event_logger.instance_flavor.info(
                'Virtual machine {instance_name} flavor has been changed to {flavor_name}.',
                event_type='iaas_instance_flavor_change_succeeded',
                event_context={'instance': instance, 'flavor': flavor},
            )

    def get_nova_usage(self, membership, start_date, end_date):
        try:
            session = self.create_session(membership=membership)
            nova = self.create_nova_client(session)

            usage = nova.usage.get(tenant_id=membership.tenant_id, start=start_date, end=end_date)
        except nova_exceptions.ClientException as e:
            logger.error('Failed to get usage for cloud project membership with id %s', membership.pk)
            six.reraise(CloudBackendError, e)
        else:
            return {
                'cpu': getattr(usage, "total_vcpus_usage", 0),
                'disk': getattr(usage, 'total_local_gb_usage', 0),
                'memory': getattr(usage, "total_memory_mb_usage", 0) / 1024,  # to get to GBs
                'servers': len(getattr(usage, "server_usages", [])),
                'server_usages': getattr(usage, "server_usages", []),
            }

    def update_tenant_name(self, membership, keystone):
        tenant_name = self.get_tenant_name(membership)

        if membership.tenant_id:
            logger.info('Trying to update name for tenant with id %s', membership.tenant_id)
            try:
                keystone.tenants.update(membership.tenant_id, name=tenant_name)
                logger.info("Successfully updated name for tenant with id %s. Tenant's new name is %s",
                            membership.tenant_id, tenant_name)
            except keystone_exceptions.NotFound as e:
                logger.warning('Tenant with id %s does not exist', membership.tenant_id)
                six.reraise(CloudBackendError, e)
        else:
            logger.warning('Cannot update tenant name for cloud project membership %s without tenant ID',
                        membership)

    # Helper methods
    def get_floating_ips(self, tenant_id, neutron):
        return neutron.list_floatingips(tenant_id=tenant_id)['floatingips']

    def push_security_group_rules(self, security_group, nova):
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
                six.reraise(CloudBackendError, e)
            else:
                logger.info('Security group rule with id %s successfully created in backend', nc_rule.id)

    def pull_security_group_rules(self, security_group, nova):
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

    def get_or_create_user(self, membership, keystone):
        # Try to sign in if credentials are already stored in membership
        User = get_user_model()

        if membership.username:
            try:
                logger.info('Signing in using stored membership credentials')
                self.create_session(membership=membership, check_tenant=False)
                logger.info('Successfully signed in, using existing user %s', membership.username)
                return membership.username, membership.password
            except keystone_exceptions.AuthorizationFailure:
                logger.info('Failed to sign in, using existing user %s', membership.username)

            username = membership.username
        else:
            username = '{0}-{1}'.format(
                self._get_project_ascii_name(membership.project),
                User.objects.make_random_password(),
            )[:self.MAX_USERNAME_LENGTH]

        # Try to create user in keystone
        password = User.objects.make_random_password()

        logger.info('Creating keystone user %s', username)
        keystone.users.create(
            name=username,
            password=password,
        )

        logger.info('Successfully created keystone user %s', username)
        return username, password

    def get_or_create_tenant(self, membership, keystone):
        tenant_name = self.get_tenant_name(membership)

        if membership.tenant_id:
            logger.info('Trying to get connected tenant with id %s', membership.tenant_id)
            try:
                return keystone.tenants.get(membership.tenant_id)
            except keystone_exceptions.NotFound:
                logger.warning('Tenant with id %s does not exist', membership.tenant_id)

        logger.info('Creating tenant %s', tenant_name)
        try:
            return keystone.tenants.create(
                tenant_name=tenant_name,
                description=membership.project.description,
            )
        except keystone_exceptions.Conflict:
            logger.info('Tenant %s already exists, using it instead', tenant_name)

        # Looks like there is a tenant already created, try to look it up
        logger.info('Looking up existing tenant %s', tenant_name)
        return keystone.tenants.find(name=tenant_name)

    def ensure_user_is_tenant_admin(self, username, tenant, keystone):
        logger.info('Assigning admin role to user %s within tenant %s',
                    username, tenant.name)

        logger.debug('Looking up cloud admin user %s', username)
        admin_user = keystone.users.find(name=username)

        logger.debug('Looking up admin role')
        admin_role = keystone.roles.find(name='admin')

        try:
            keystone.roles.add_user_role(
                user=admin_user.id,
                role=admin_role.id,
                tenant=tenant.id,
            )
        except keystone_exceptions.Conflict:
            logger.info('User %s already has admin role within tenant %s',
                        username, tenant.name)

    def get_or_create_internal_network(self, membership, neutron):

        logger.info('Checking internal network of tenant %s', membership.tenant_id)
        if membership.internal_network_id:
            try:
                # check if the network actually exists
                response = neutron.show_network(membership.internal_network_id)
            except neutron_exceptions.NeutronClientException as e:
                logger.exception('Internal network with id %s does not exist. Stale data in database?',
                                 membership.internal_network_id)
                six.reraise(CloudBackendError, e)
            else:
                logger.info('Internal network with id %s exists.', membership.internal_network_id)

                network_name = response['network']['name']
                subnet_id = response['network']['subnets'][0]
                self.get_or_create_router(neutron, network_name, subnet_id, membership.tenant_id)

            return membership.internal_network_id

        network_name = self.get_tenant_internal_network_name(membership)
        networks = neutron.list_networks(name=network_name)['networks']

        if networks:
            network = networks[0]
            membership.internal_network_id = network['id']
            membership.save()
            logger.info('Internal network %s for tenant %s already exists.', network_name, membership.tenant_id)

            subnet_id = network['subnets'][0]
            self.get_or_create_router(neutron, network_name, subnet_id, membership.tenant_id)
        else:
            network = {
                'name': network_name,
                'tenant_id': membership.tenant_id,
            }

            # in case nothing fits, create and persist internal network
            create_response = neutron.create_network({'networks': [network]})
            network_id = create_response['networks'][0]['id']
            membership.internal_network_id = network_id
            membership.save()
            logger.info('Internal network %s was created for tenant %s.', network_name, membership.tenant_id)

            subnet_name = '{0}-subnet01'.format(network_name)

            logger.info('Creating subnet %s', subnet_name)
            subnet_data = {
                'network_id': membership.internal_network_id,
                'tenant_id': membership.tenant_id,
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
            self.get_or_create_router(neutron, network_name, create_response['subnets'][0]['id'],
                                      membership.tenant_id)

        return membership.internal_network_id

    def connect_membership_to_external_network(self, membership, external_network_id, neutron):
        """ Create router that will connect external network and memberships tenant """
        try:
            # check if the network actually exists
            response = neutron.show_network(external_network_id)
        except neutron_exceptions.NeutronClientException as e:
            logger.exception('External network with id %s does not exist. Stale data in database?', external_network_id)
            six.reraise(CloudBackendError, e)
        else:

            network_name = response['network']['name']
            subnet_id = response['network']['subnets'][0]
            # XXX: refactor function call, split get_or_create_router into more fine grained
            self.get_or_create_router(neutron, network_name, subnet_id, membership.tenant_id,
                                      external=True, network_id=response['network']['id'])

            membership.external_network_id = external_network_id
            membership.save()

            logger.info('Router between external network %s and tenant %s was successfully created',
                        external_network_id, membership.tenant_id)
            return external_network_id

    def get_or_create_external_network(self, membership, neutron, network_ip, network_prefix,
                                       vlan_id=None, vxlan_id=None, ips_count=None):
        if membership.external_network_id:
            self.connect_membership_to_external_network(membership, membership.external_network_id, neutron)

        # External network creation
        network_name = '{0}-ext-net'.format(self.create_backend_name())
        network = {
            'name': network_name,
            'tenant_id': membership.tenant_id,
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
            raise CloudBackendError('VLAN or VXLAN ID should be provided.')

        create_response = neutron.create_network({'networks': [network]})
        network_id = create_response['networks'][0]['id']
        logger.info('External network with name %s has been created.', network_name)
        membership.external_network_id = network_id
        membership.save()

        # Subnet creation
        subnet_name = '{0}-sn01'.format(network_name)
        cidr = '{0}/{1}'.format(network_ip, network_prefix)

        subnet_data = {
            'network_id': membership.external_network_id,
            'tenant_id': membership.tenant_id,
            'cidr': cidr,
            'name': subnet_name,
            'ip_version': 4,
            'enable_dhcp': False,
        }
        create_response = neutron.create_subnet({'subnets': [subnet_data]})
        logger.info('Subnet with name %s has been created.', subnet_name)

        # Router creation
        self.get_or_create_router(neutron, network_name, create_response['subnets'][0]['id'],
                                  membership.tenant_id)

        # Floating IPs creation
        floating_ip = {
            'floating_network_id': membership.external_network_id,
        }

        if vlan_id is not None and ips_count is not None:
            for i in range(ips_count):
                ip = neutron.create_floatingip({'floatingip': floating_ip})['floatingip']
                logger.info('Floating ip %s for external network %s has been created.',
                            ip['floating_ip_address'], network_name)

        return membership.external_network_id

    def detect_external_network(self, membership, neutron):
        routers = neutron.list_routers(tenant_id=membership.tenant_id)['routers']
        if bool(routers):
            router = routers[0]
        else:
            logger.warning('Cloud project membership %s does not have connected routers.', membership)
            return

        ext_gw = router.get('external_gateway_info', {})
        if 'network_id' in ext_gw:
            membership.external_network_id = ext_gw['network_id']
            membership.save()
            logger.info('Found and set external network with id %s', ext_gw['network_id'])

    def delete_external_network(self, membership, neutron):
        floating_ips = neutron.list_floatingips(floating_network_id=membership.external_network_id)['floatingips']

        for ip in floating_ips:
            neutron.delete_floatingip(ip['id'])
            logger.info('Floating IP with id %s has been deleted.', ip['id'])

        ports = neutron.list_ports(network_id=membership.external_network_id)['ports']
        for port in ports:
            neutron.remove_interface_router(port['device_id'], {'port_id': port['id']})
            logger.info('Port with id %s has been deleted.', port['id'])

        subnets = neutron.list_subnets(network_id=membership.external_network_id)['subnets']
        for subnet in subnets:
            neutron.delete_subnet(subnet['id'])
            logger.info('Subnet with id %s has been deleted.', subnet['id'])

        neutron.delete_network(membership.external_network_id)
        logger.info('External network with id %s has been deleted.', membership.external_network_id)
        membership.external_network_id = ''
        membership.save()

    def get_or_create_router(self, neutron, network_name, subnet_id, tenant_id, external=False, network_id=None):
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

    def get_hypervisors_statistics(self, nova):
        return nova.hypervisors.statistics()._info

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

    def _get_project_ascii_name(self, project):
        return ''.join([c for c in project.name if ord(c) < 128])

    def get_tenant_name(self, membership):
        return '%(project_name)s-%(project_uuid)s' % {
            'project_name': self._get_project_ascii_name(membership.project)[:15],
            'project_uuid': membership.project.uuid.hex[:4]
        }

    def get_tenant_internal_network_name(self, membership):
        tenant_name = self.get_tenant_name(membership)
        return '{0}-int-net'.format(tenant_name)

    def create_backend_name(self):
        return 'nc-{0}'.format(uuid.uuid4().hex)

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

    def _wait_for_instance_deletion(self, backend_instance_id, nova, retries=90, poll_interval=3):
        try:
            for _ in range(retries):
                nova.servers.get(backend_instance_id)
                time.sleep(poll_interval)

            return False
        except nova_exceptions.NotFound:
            return True

    def _attach_volume(self, nova, cinder, server_id, volume_id, instance_uuid):
        nova.volumes.create_server_volume(server_id, volume_id, None)
        if not self._wait_for_volume_status(volume_id, cinder, 'in-use', 'error'):
            logger.error(
                'Failed to extend volume: timed out waiting volume %s to attach to instance %s',
                volume_id, instance_uuid,
            )
            raise CloudBackendError(
                'Timed out waiting volume %s to attach to instance %s'
                % (volume_id, instance_uuid)
            )

    def _detach_volume(self, nova, cinder, server_id, volume_id, instance_uuid):
        nova.volumes.delete_server_volume(server_id, volume_id)
        if not self._wait_for_volume_status(volume_id, cinder, 'available', 'error'):
            logger.error(
                'Failed to extend volume: timed out waiting volume %s to detach from instance %s',
                volume_id, instance_uuid,
            )
            raise CloudBackendError(
                'Timed out waiting volume %s to detach from instance %s'
                % (volume_id, instance_uuid)
            )

    def _extend_volume(self, cinder, volume, new_backend_size):
        cinder.volumes.extend(volume, new_backend_size)
        if not self._wait_for_volume_status(volume.id, cinder, 'available', 'error'):
            logger.error(
                'Failed to extend volume: timed out waiting volume %s to extend',
                volume.id,
            )
            raise CloudBackendError(
                'Timed out waiting volume %s to extend'
                % volume.id,
            )

    def push_floating_ip_to_instance(self, server, instance, nova):
        if not instance.external_ips or not instance.internal_ips:
            return

        logger.debug('About to add external ip %s to instance %s',
                     instance.external_ips, instance.uuid)

        membership = instance.cloud_project_membership
        try:
            floating_ip = membership.floating_ips.get(
                status__in=('BOOKED', 'DOWN'),
                address=instance.external_ips,
                backend_network_id=membership.external_network_id
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
            instance.save()
        else:
            floating_ip.status = 'ACTIVE'
            floating_ip.save()
            logger.info('Successfully added external ip %s to instance %s',
                        instance.external_ips, instance.uuid)

    def release_floating_ip_from_instance(self, instance):
        if not instance.external_ips:
            return

        membership = instance.cloud_project_membership
        try:
            floating_ip = membership.floating_ips.get(
                status='ACTIVE',
                address=instance.external_ips,
                backend_network_id=membership.external_network_id
            )
        except (ObjectDoesNotExist, MultipleObjectsReturned):
            logger.warning('Failed to release floating ip %s from instance %s',
                           instance.external_ips, instance.uuid)
        else:
            floating_ip.status = 'DOWN'
            floating_ip.save()
            logger.info('Successfully released floating ip %s from instance %s',
                        instance.external_ips, instance.uuid)

    def allocate_floating_ip_address(self, neutron, membership):
        try:
            data = {'floating_network_id': membership.external_network_id, 'tenant_id': membership.tenant_id}
            ip_address = neutron.create_floatingip({'floatingip': data})['floatingip']
        except neutron_exceptions.NeutronClientException as e:
            logger.exception('Unable to allocate floating IP address in external network %s',
                             membership.external_network_id)
            six.reraise(CloudBackendError, e)
        else:
            membership.floating_ips.create(
                status='DOWN',
                address=ip_address['floating_ip_address'],
                backend_id=ip_address['id'],
                backend_network_id=ip_address['floating_network_id']
            )
            logger.info('Floating IP %s for external network with id %s has been created.',
                        ip_address['floating_ip_address'], membership.external_network_id)

    def assign_floating_ip_to_instance(self, nova, instance, floating_ip):
        nova.servers.add_floating_ip(server=instance.backend_id, address=floating_ip.address)

        floating_ip.status = 'ACTIVE'
        floating_ip.save()

        instance.external_ips = floating_ip.address
        instance.save()

        logger.info('Floating IP %s was successfully assigned to the instance with id %s.',
                    floating_ip.address, instance.uuid)

    def get_attached_volumes(self, server_id, nova):
        """
        Returns attached volumes for specified vm instance

        :param server_id: vm instance id
        :type server_id: str
        :returns: list of class 'Volume'
        :rtype: list
        """
        return nova.volumes.get_server_volumes(server_id)

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
            raise CloudBackendInternalError()

        logger.info('Successfully created snapshot %s for volume %s', snapshot.id, volume_id)

        return snapshot

    def delete_snapshot(self, snapshot_id, cinder):
        """
        Delete a snapshot

        :param snapshot_id: snapshot id
        :type snapshot_id: str
        """
        logger.debug('About to delete a snapshot %s', snapshot_id)

        if not self._wait_for_snapshot_status(snapshot_id, cinder, 'available', 'error', poll_interval=60, retries=30):
            logger.exception('Timed out waiting for snapshot %s to become available', snapshot_id)
            raise CloudBackendInternalError()

        cinder.volume_snapshots.delete(snapshot_id)
        logger.info('Successfully deleted a snapshot %s', snapshot_id)

    def create_volume_from_snapshot(self, snapshot_id, cinder, prefix='Promoted volume'):
        """
        Create a volume from snapshot

        :param snapshot_id: snapshot id
        :type snapshot_id: str
        :returns: volume id
        :rtype: str
        """
        snapshot = cinder.volume_snapshots.get(snapshot_id)
        volume_size = snapshot.size
        volume_name = prefix + (' %s' % snapshot.volume_id)

        logger.debug('About to create temporary volume from snapshot %s', snapshot_id)
        created_volume = cinder.volumes.create(volume_size, snapshot_id=snapshot_id,
                                               display_name=volume_name)
        volume_id = created_volume.id

        if not self._wait_for_volume_status(volume_id, cinder, 'available', 'error'):
            logger.error('Timed out creating temporary volume from snapshot %s', snapshot_id)
            raise CloudBackendInternalError()

        logger.info('Successfully created temporary volume %s from snapshot %s',
                    volume_id, snapshot_id)

        return volume_id

    def delete_volume(self, volume_id, cinder):
        """
        Delete temporary volume

        :param volume_id: volume ID
        :type volume_id: str
        """
        logger.debug('About to delete volume %s' % volume_id)
        if not self._wait_for_volume_status(volume_id, cinder, 'available', 'error', poll_interval=20):
            logger.exception('Timed out waiting volume %s availability', volume_id)
            raise CloudBackendInternalError()

        cinder.volumes.delete(volume_id)
        logger.info('Volume successfully deleted.')

    def get_backup_info(self, backup_id, cinder):
        """
        Returns backup info

        :param backup_id: backup id
        :type backup_id: str
        :returns: backup info dict
        :rtype: dict
        """
        backup_info = cinder.backups.get(backup_id)

        return {
            'name': backup_info.name,
            'status': backup_info.status,
            'description': backup_info.description
        }

    def create_volume_backup(self, volume_id, bckp_desc, cinder):
        """
        Create backup from temporary volume

        :param volume_id: temporary volume id
        :type volume_id: str
        :param bckp_desc: backup description
        :type bckp_desc: str
        :returns: backup id
        :rtype: str
        """
        backup_name = 'Backup_created_from_volume_%s' % volume_id

        logger.debug('About to create backup from temporary volume %s' % volume_id)

        if not self._wait_for_volume_status(volume_id, cinder, 'available', 'error'):
            logger.exception('Timed out waiting volume %s availability', volume_id)
            raise CloudBackendInternalError()

        backup_volume = cinder.backups.create(volume_id, name=backup_name, description=bckp_desc)
        logger.info('Backup from temporary volume %s was created successfully', volume_id)
        return backup_volume.id

    def restore_volume_backup(self, backup_id, cinder):
        """
        Restore volume from backup

        :param backup_id: backup id
        :type backup_id: str
        :returns: volume id
        :rtype: str
        """
        logger.debug('About to restore backup %s', backup_id)

        if not self._wait_for_backup_status(backup_id, cinder, 'available', 'error'):
            logger.exception('Timed out waiting backup %s availability', backup_id)
            raise CloudBackendInternalError()

        restore = cinder.restores.restore(backup_id)

        logger.debug('About to restore volume from backup %s', backup_id)
        volume_id = restore.volume_id

        if not self._wait_for_volume_status(volume_id, cinder, 'available', 'error_restoring', poll_interval=20):
            logger.exception('Timed out waiting volume %s restoring', backup_id)
            raise CloudBackendInternalError()

        logger.info('Restored volume %s', volume_id)
        logger.info('Restored backup %s', backup_id)
        return volume_id

    def delete_backup(self, backup_id, cinder):
        """
        :param backup_id: backup id
        :type backup_id: str
        """
        backup = cinder.backups.get(backup_id)

        logger.debug('About to delete backup %s', backup_id)

        if not self._wait_for_backup_status(backup_id, cinder, 'available', 'error'):
            logger.exception('Timed out waiting backup %s availability. Status: %s', backup_id, backup.status)
            raise CloudBackendInternalError()
        else:
            cinder.backups.delete(backup_id)

        logger.info('Deleted backup %s', backup_id)

    def create_vm(self, server_id, device_map, nova):
        """
        Create new vm instance using restored volumes
        :param server_id: vm instance id
        :type server_id: str
        :returns: vm instance id
        :rtype: str
        """
        server = nova.servers.get(server_id)
        new_server_name = 'Restored_%s' % server.name
        flavor = nova.flavors.get(server.flavor.get('id'))

        new_server = nova.servers.create(new_server_name, None, flavor, block_device_mapping=device_map)

        logger.debug('About to create new vm instance %s', new_server.id)

        # TODO: ask about complete status
        while new_server.status == 'BUILD':
            time.sleep(5)
            new_server = nova.servers.get(new_server.id)

        logger.info('VM instance %s creation completed', new_server.id)

        return new_server.id

    def _are_rules_equal(self, backend_rule, nc_rule):
        """
        Check equality of significant parameters in openstack and nodeconductor rules
        """
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

    def _get_instance_volumes(self, nova, cinder, backend_instance_id):
        try:
            attached_volume_ids = [
                v.volumeId
                for v in nova.volumes.get_server_volumes(backend_instance_id)
            ]

            if len(attached_volume_ids) != 2:
                logger.info('Skipping instance %s, only instances with 2 volumes are supported, found %d',
                            backend_instance_id, len(attached_volume_ids))
                raise LookupError

            attached_volumes = [
                cinder.volumes.get(volume_id)
                for volume_id in attached_volume_ids
            ]

            # Blessed be OpenStack developers for returning booleans as strings
            system_volume = next(v for v in attached_volumes if v.bootable == 'true')
            data_volume = next(v for v in attached_volumes if v.bootable == 'false')
        except (cinder_exceptions.ClientException, StopIteration) as e:
            logger.info('Skipping instance %s, failed to fetch volumes', backend_instance_id)
            six.reraise(LookupError, e)
        else:
            return system_volume, data_volume

    def _get_instance_template(self, system_volume, membership, backend_instance_id):
        try:
            image_id = system_volume.volume_image_metadata['image_id']

            return models.Template.objects.get(
                images__backend_id=image_id,
                images__cloud__cloudprojectmembership=membership,
            )
        except (KeyError, AttributeError):
            logger.info('Skipping instance %s, failed to infer template',
                        backend_instance_id)
            raise LookupError
        except (models.Template.DoesNotExist, models.Template.MultipleObjectsReturned):
            logger.info('Skipping instance %s, failed to infer template',
                        backend_instance_id)
            raise LookupError

    def _get_flavor_info(self, nova, backend_instance):
        try:
            flavor_id = backend_instance.flavor['id']
            flavor = nova.flavors.get(flavor_id)
        except (KeyError, AttributeError):
            logger.info('Skipping instance %s, failed to infer flavor info',
                        backend_instance.id)
            raise LookupError
        except nova_exceptions.ClientException as e:
            logger.info('Skipping instance %s, failed to infer flavor info',
                        backend_instance.id)
            six.reraise(LookupError, e)
        else:
            cores = flavor.vcpus
            ram = self.get_core_ram_size(flavor.ram)
            return cores, ram, flavor.name

    def _normalize_security_group_rule(self, rule):
        if rule['ip_protocol'] is None:
            rule['ip_protocol'] = ''

        if 'cidr' not in rule['ip_range']:
            rule['ip_range']['cidr'] = '0.0.0.0/0'

        return rule

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
            # TODO: VERIFY_RESIZE --> perhaps OFFLINE? resize is an offline procedure for flavor change
            'VERIFY_RESIZE': models.Instance.States.ONLINE,
        }
        return nova_to_nodeconductor.get(instance.status,
                                         models.Instance.States.ERRED)

    def _get_instance_start_time(self, instance):
        try:
            launch_time = instance.to_dict()['OS-SRV-USG:launched_at']
            d = dateparse.parse_datetime(launch_time)
        except (KeyError, ValueError):
            return None
        else:
            # At the moment OpenStack does not provide any timezone info,
            # but in future it might do.
            if timezone.is_naive(d):
                d = timezone.make_aware(d, timezone.utc)
            return d

    def _get_instance_ips(self, backend_instance):
        extracted_ips = {}
        for _, net_conf in backend_instance.addresses.items():
            for ip in net_conf:
                if ip['OS-EXT-IPS:type'] == 'fixed':
                    extracted_ips['internal'] = ip['addr']
                    continue
                if ip['OS-EXT-IPS:type'] == 'floating':
                    extracted_ips['external'] = ip['addr']
                    continue
        return extracted_ips
