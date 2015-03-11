# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging
import functools
import dateutil.parser

from datetime import timedelta

from django.conf import settings
from django.utils import six, timezone
from celery import shared_task

from keystoneclient import session as keystone_session
from keystoneclient.auth.identity import v2
from keystoneclient.service_catalog import ServiceCatalog
from keystoneclient.v2_0 import client as keystone_client
from neutronclient.v2_0 import client as neutron_client
from novaclient.v1_1 import client as nova_client
from glanceclient.v1 import client as glance_client

from nodeconductor.iaas.models import Instance
from nodeconductor.iaas.backend import CloudBackendError
from nodeconductor.core.tasks import retry_if_false


logger = logging.getLogger(__name__)


class OpenStack(object):

    @classmethod
    def create_session(cls, keystone_url=None, instance_uuid=None, user=None):
        credentials = None
        if keystone_url:
            credentials = cls._get_keystone_credentials(keystone_url)
        elif instance_uuid:
            credentials = cls._get_instance_credentials(instance_uuid, user)

        if not credentials:
            raise CloudBackendError('Missing OpenStack credentials')

        auth_plugin = v2.Password(**credentials)
        ks_session = keystone_session.Session(auth=auth_plugin)

        # This will eagerly sign in throwing AuthorizationFailure on bad credentials
        ks_session.get_token()

        options = ('auth_ref', 'auth_url', 'username', 'password', 'tenant_id', 'tenant_name')
        session = dict((opt, getattr(ks_session.auth, opt)) for opt in options)

        return session

    @staticmethod
    def is_valid_session(session):
        if session and session['auth_ref']:
            expiresat = dateutil.parser.parse(session['auth_ref']['token']['expires'])
            if expiresat > timezone.now() + timedelta(minutes=1):
                return True

        return False

    @staticmethod
    def _get_keystone_credentials(keystone_url):
        nc_settings = getattr(settings, 'NODECONDUCTOR', {})
        openstacks = nc_settings.get('OPENSTACK_CREDENTIALS', ())

        try:
            credentials = next(o for o in openstacks if o['auth_url'] == keystone_url)
        except StopIteration as e:
            logger.exception('Failed to find OpenStack credentials for Keystone URL %s', keystone_url)
            six.reraise(CloudBackendError, e)

        return credentials

    @staticmethod
    def _get_instance_credentials(instance_uuid, user=None):
        instance = Instance.objects.get(uuid=instance_uuid)
        membership = instance.cloud_project_membership
        credentials = {
            'auth_url': membership.cloud.auth_url,
            'username': membership.username,
            'password': membership.password,
        }
        if not user:
            credentials['tenant_id'] = membership.tenant_id

        return credentials

    @staticmethod
    def keystone(session):
        return keystone_client.Client(auth_ref=session['auth_ref'])

    @staticmethod
    def nova(session):
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

    @staticmethod
    def neutron(session):
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

    @staticmethod
    def glance(session):
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
        if not OpenStack.is_valid_session(session):
            raise CloudBackendError('Invalid OpenStack session')
        task_fn(session, *args, **kwargs)
        return session
    return wrapped


@shared_task
def create_openstack_session(keystone_url=None, instance_uuid=None):
    return OpenStack.create_session(keystone_url=keystone_url, instance_uuid=instance_uuid)


@shared_task
@track_openstack_session
def nova_server_resize(session, server_id, flavor_id):
    OpenStack.nova(session).servers.resize(server_id, flavor_id, 'MANUAL')


@shared_task
@track_openstack_session
def nova_server_resize_confirm(session, server_id):
    OpenStack.nova(session).servers.confirm_resize(server_id)


@shared_task(max_retries=300, default_retry_delay=3)
@track_openstack_session
@retry_if_false
def nova_wait_for_server_status(session, server_id, status):
    server = OpenStack.nova(session).servers.get(server_id)
    return server.status == status
