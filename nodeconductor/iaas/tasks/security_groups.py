# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging

from celery import shared_task

from nodeconductor.core.tasks import transition
from nodeconductor.iaas.tasks.openstack import (
    openstack_create_security_group, openstack_update_security_group, openstack_delete_security_group)
from nodeconductor.iaas.models import SecurityGroup

logger = logging.getLogger(__name__)


@shared_task(name='nodeconductor.iaas.create_security_group')
@transition(SecurityGroup, 'begin_syncing')
def create_security_group(security_group_uuid, transition_entity=None):
    openstack_create_security_group.apply_async(
        args=(security_group_uuid,),
        link=security_group_sync_succeeded.si(security_group_uuid),
        link_error=security_group_sync_failed.si(security_group_uuid),
    )


@shared_task(name='nodeconductor.iaas.update_security_group')
@transition(SecurityGroup, 'begin_syncing')
def update_security_group(security_group_uuid, transition_entity=None):
    openstack_update_security_group.apply_async(
        args=(security_group_uuid,),
        link=security_group_sync_succeeded.si(security_group_uuid),
        link_error=security_group_sync_failed.si(security_group_uuid),
    )


@shared_task(name='nodeconductor.iaas.delete_security_group')
@transition(SecurityGroup, 'begin_syncing')
def delete_security_group(security_group_uuid, transition_entity=None):
    openstack_delete_security_group.apply_async(
        args=(security_group_uuid,),
        link=security_group_deletion_succeeded.si(security_group_uuid),
        link_error=security_group_sync_failed.si(security_group_uuid),
    )


@shared_task
@transition(SecurityGroup, 'set_in_sync')
def security_group_sync_succeeded(security_group_uuid, transition_entity=None):
    pass


@shared_task
@transition(SecurityGroup, 'set_erred')
def security_group_sync_failed(security_group_uuid, transition_entity=None):
    pass


@shared_task
def security_group_deletion_succeeded(security_group_uuid):
    SecurityGroup.objects.get(uuid=security_group_uuid).delete()
