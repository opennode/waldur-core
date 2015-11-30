# -*- coding: utf-8 -*-
from __future__ import absolute_import

import functools

from celery import shared_task

from nodeconductor.iaas.models import Instance, SecurityGroup
from nodeconductor.iaas.backend import OpenStackBackend
from nodeconductor.core.tasks import throttle, retry_if_false


def track_openstack_session(task_fn):
    @functools.wraps(task_fn)
    def wrapped(tracked_session, *args, **kwargs):
        session = OpenStackBackend.recover_session(tracked_session)
        session.validate()
        task_fn(session, *args, **kwargs)
        return session
    return wrapped


@shared_task
def openstack_create_session(**kwargs):
    return OpenStackBackend.create_session(**kwargs)


@shared_task
@track_openstack_session
def nova_server_resize(session, server_id, flavor_id):
    OpenStackBackend.create_nova_client(session).servers.resize(server_id, flavor_id, 'MANUAL')


@shared_task
@track_openstack_session
def nova_server_resize_confirm(session, server_id):
    OpenStackBackend.create_nova_client(session).servers.confirm_resize(server_id)


@shared_task(max_retries=300, default_retry_delay=3)
@track_openstack_session
@retry_if_false
def nova_wait_for_server_status(session, server_id, status):
    server = OpenStackBackend.create_nova_client(session).servers.get(server_id)
    return server.status == status


@shared_task(is_heavy_task=True)
def openstack_provision_instance(instance_uuid, backend_flavor_id,
                                 system_volume_id=None, data_volume_id=None):
    instance = Instance.objects.get(uuid=instance_uuid)
    cloud = instance.cloud_project_membership.cloud

    with throttle(key=cloud.auth_url):
        # TODO: split it into a series of smaller tasks
        backend = cloud.get_backend()
        backend.provision_instance(
            instance, backend_flavor_id, system_volume_id, data_volume_id)


@shared_task
@track_openstack_session
def openstack_create_security_group(session, security_group_uuid):
    security_group = SecurityGroup.objects.get(uuid=security_group_uuid)
    backend = security_group.cloud_project_membership.cloud.get_backend()
    nova = OpenStackBackend.create_nova_client(session)
    backend.create_security_group(security_group, nova=nova)


@shared_task
@track_openstack_session
def openstack_update_security_group(session, security_group_uuid):
    security_group = SecurityGroup.objects.get(uuid=security_group_uuid)
    backend = security_group.cloud_project_membership.cloud.get_backend()
    nova = OpenStackBackend.create_nova_client(session)
    backend.update_security_group(security_group, nova=nova)


@shared_task
@track_openstack_session
def openstack_delete_security_group(session, security_group_uuid):
    security_group = SecurityGroup.objects.get(uuid=security_group_uuid)
    backend = security_group.cloud_project_membership.cloud.get_backend()
    nova = OpenStackBackend.create_nova_client(session)
    backend.delete_security_group(security_group.backend_id, nova=nova)
