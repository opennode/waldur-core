# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging

from celery import shared_task, chain

from nodeconductor.core.log import EventLoggerAdapter
from nodeconductor.core.tasks import transition
from nodeconductor.iaas.models import Instance
from nodeconductor.iaas.tasks.openstack import (
    openstack_create_session, nova_wait_for_server_status,
    nova_server_resize, nova_server_resize_confirm)


logger = logging.getLogger(__name__)
event_logger = EventLoggerAdapter(logger)


@shared_task(name='nodeconductor.iaas.resize_flavor')
@transition(Instance, 'begin_resizing')
def resize_flavor(instance_uuid, flavor_uuid, transition_entity=None):
    instance = transition_entity
    cloud = instance.cloud_project_membership.cloud
    flavor = cloud.flavors.get(uuid=flavor_uuid)
    server_id = instance.backend_id
    flavor_id = flavor.backend_id

    chain(
        openstack_create_session.s(instance_uuid=instance_uuid, dummy=cloud.dummy),
        nova_server_resize.s(server_id, flavor_id),
        nova_wait_for_server_status.s(server_id, 'VERIFY_RESIZE'),
        nova_server_resize_confirm.s(server_id),
        nova_wait_for_server_status.s(server_id, 'SHUTOFF'),
    ).apply_async(
        link=flavor_change_succeeded.si(instance_uuid, flavor_uuid),
        link_error=flavor_change_failed.si(instance_uuid),
    )


@shared_task
@transition(Instance, 'set_offline')
def flavor_change_succeeded(instance_uuid, flavor_uuid, transition_entity=None):
    instance = transition_entity
    flavor = instance.cloud_project_membership.cloud.flavors.get(uuid=flavor_uuid)
    logger.info('Successfully changed flavor of an instance %s', instance.uuid)
    event_logger.info(
        'Virtual machine %s flavor has been changed to %s.', instance.name, flavor.name,
        extra={'instance': instance, 'event_type': 'iaas_instance_flavor_change_succeeded'},
    )


@shared_task
@transition(Instance, 'set_erred')
def flavor_change_failed(instance_uuid, transition_entity=None):
    instance = transition_entity
    logger.exception('Failed to change flavor of an instance %s', instance.uuid)
    event_logger.error(
        'Virtual machine %s flavor change has failed.', instance.name,
        extra={'instance': instance, 'event_type': 'iaas_instance_flavor_change_failed'},
    )
