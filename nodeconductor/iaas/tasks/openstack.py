# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging
import functools
import pkg_resources
import dateutil.parser

from datetime import timedelta

from django.utils import six, timezone
from django.utils.lru_cache import lru_cache
from celery import shared_task

from keystoneclient import session as keystone_session
from keystoneclient.auth.identity import v2
from keystoneclient.service_catalog import ServiceCatalog
from keystoneclient.v2_0 import client as keystone_client
from neutronclient.v2_0 import client as neutron_client
from novaclient.v1_1 import client as nova_client
from glanceclient.v1 import client as glance_client
from cinderclient.v1 import client as cinder_client

from nodeconductor.iaas.models import Instance, OpenStackSettings
from nodeconductor.iaas.backend import CloudBackendError
from nodeconductor.iaas.backend.openstack import OpenStackBackend
from nodeconductor.core.tasks import throttle, retry_if_false


logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_cinder_version():
    try:
        return pkg_resources.get_distribution('python-cinderclient').parsed_version
    except ValueError:
        return '00000001', '00000000', '00000009', '*final'


@lru_cache(maxsize=1)
def _get_neutron_version():
    try:
        return pkg_resources.get_distribution('python-neutronclient').parsed_version
    except ValueError:
        return '00000002', '00000003', '00000004', '*final'


@lru_cache(maxsize=1)
def _get_nova_version():
    try:
        return pkg_resources.get_distribution('python-novaclient').parsed_version
    except ValueError:
        return '00000002', '00000017', '00000000', '*final'


class OpenStackClient(object):

    @staticmethod
    def create_session(**credentials):
        ks_session = keystone_session.Session(auth=v2.Password(**credentials))

        # This will eagerly sign in throwing AuthorizationFailure on bad credentials
        ks_session.get_token()

        # There's a temporary need to pass plain credentials
        # Currently packaged libraries novaclient==2.17.0, neutronclient==2.3.4
        # and cinderclient==1.0.9 don't support token auth.
        # TODO: Switch to token auth on libraries upgrade.
        options = ('auth_ref', 'auth_url', 'username', 'password', 'tenant_id', 'tenant_name')
        session = {opt: getattr(ks_session.auth, opt) for opt in options}

        return session

    @staticmethod
    def recover_session(session):
        return keystone_session.Session(
            auth=v2.Token(
                auth_url=session['auth_url'],
                token=session['auth_ref']['token']['id']))

    @staticmethod
    def is_valid_session(session):
        if session and session['auth_ref']:
            expiresat = dateutil.parser.parse(session['auth_ref']['token']['expires'])
            if expiresat > timezone.now() + timedelta(minutes=1):
                return True

        return False

    @classmethod
    def create_admin_session(cls, keystone_url):
        try:
            credentials = OpenStackSettings.objects.get(auth_url=keystone_url).get_credentials()
        except OpenStackSettings.DoesNotExist as e:
            logger.exception('Failed to find OpenStack credentials for Keystone URL %s', keystone_url)
            six.reraise(CloudBackendError, e)

        return cls.create_session(**credentials)

    @classmethod
    def create_tenant_session(cls, credentials):
        return cls.create_session(**credentials)

    @classmethod
    def create_keystone_client(cls, session):
        return keystone_client.Client(auth_ref=session['auth_ref'])

    @classmethod
    def create_nova_client(cls, session):
        if _get_nova_version() >= pkg_resources.parse_version('2.18.0'):
            return nova_client.Client(session=cls.recover_session(session))

        kwargs = {
            'auth_url': session['auth_url'],
            'username': session['username'],
            'api_key': session['password'],
            'tenant_id': session['tenant_id'],
            # project_id is tenant_name, id doesn't make sense,
            # pretty usual for OpenStack
            'project_id': session['tenant_name'],
        }

        return nova_client.Client(**kwargs)

    @classmethod
    def create_neutron_client(cls, session):
        if _get_neutron_version() >= pkg_resources.parse_version('2.3.6'):
            return neutron_client.Client(session=cls.recover_session(session))

        kwargs = {
            'auth_url': session['auth_url'],
            'username': session['username'],
            'password': session['password'],
            'tenant_id': session['tenant_id'],
            # neutron is different in a sense it is more reasonable to call
            # tenant_name a tenant_name, rather then project_id
            'tenant_name': session['tenant_name'],
        }

        return neutron_client.Client(**kwargs)

    @classmethod
    def create_cinder_client(cls, session):
        if _get_cinder_version() >= pkg_resources.parse_version('1.1.0'):
            return cinder_client.Client(session=cls.recover_session(session))

        kwargs = {
            'auth_url': session['auth_url'],
            'username': session['username'],
            'api_key': session['password'],
            'tenant_id': session['tenant_id'],
            # project_id is tenant_name, id doesn't make sense,
            # pretty usual for OpenStack
            'project_id': session['tenant_name'],
        }

        return cinder_client.Client(**kwargs)

    @classmethod
    def create_glance_client(cls, session):
        catalog = ServiceCatalog.factory(session['auth_ref'])
        endpoint = catalog.url_for(service_type='image')

        kwargs = {
            'token': session['auth_ref']['token']['id'],
            'insecure': False,
            'timeout': 600,
            'ssl_compression': True,
        }

        return glance_client.Client(endpoint, **kwargs)


def track_openstack_session(task_fn):
    @functools.wraps(task_fn)
    def wrapped(session, *args, **kwargs):
        if not OpenStackClient.is_valid_session(session):
            raise CloudBackendError('Invalid OpenStack session')
        task_fn(session, *args, **kwargs)
        return session
    return wrapped


@shared_task
def openstack_create_session(keystone_url=None, instance_uuid=None, check_tenant=True):
    if keystone_url:
        return OpenStackClient.create_admin_session(keystone_url)

    elif instance_uuid:
        instance = Instance.objects.get(uuid=instance_uuid)
        membership = instance.cloud_project_membership
        credentials = {
            'auth_url': membership.cloud.auth_url,
            'username': membership.username,
            'password': membership.password,
        }
        if check_tenant:
            credentials['tenant_id'] = membership.tenant_id

        return OpenStackClient.create_tenant_session(credentials)

    raise CloudBackendError('Missing OpenStack credentials')


@shared_task
@track_openstack_session
def nova_server_resize(session, server_id, flavor_id):
    OpenStackClient.create_nova_client(session).servers.resize(server_id, flavor_id, 'MANUAL')


@shared_task
@track_openstack_session
def nova_server_resize_confirm(session, server_id):
    OpenStackClient.create_nova_client(session).servers.confirm_resize(server_id)


@shared_task(max_retries=300, default_retry_delay=3)
@track_openstack_session
@retry_if_false
def nova_wait_for_server_status(session, server_id, status):
    server = OpenStackClient.create_nova_client(session).servers.get(server_id)
    return server.status == status


@shared_task(is_heavy_task=True)
def openstack_provision_instance(instance_uuid, backend_flavor_id,
                                 system_volume_id=None, data_volume_id=None):
    instance = Instance.objects.get(uuid=instance_uuid)

    with throttle(key=instance.cloud_project_membership.cloud.auth_url):
        # TODO: split it into a series of smaller tasks
        OpenStackBackend.provision_instance(
            instance, backend_flavor_id, system_volume_id, data_volume_id)
