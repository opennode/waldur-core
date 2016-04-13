import logging

from celery import chain, shared_task

from nodeconductor.core.tasks import transition
from nodeconductor.openstack.models import Instance, Flavor
from nodeconductor.structure.log import event_logger

from .base import (
    nova_server_resize, nova_server_resize_confirm,
    nova_wait_for_server_status, save_error_message_from_task)

logger = logging.getLogger(__name__)


@shared_task(name='nodeconductor.openstack.change_flavor')
@transition(Instance, 'begin_resizing')
def change_flavor(instance_uuid, flavor_uuid, transition_entity=None):
    instance = transition_entity
    backend = instance.get_backend()
    client = backend.get_client()
    flavor = Flavor.objects.get(
        settings=instance.service_project_link.service.settings,
        uuid=flavor_uuid)

    instance.ram = flavor.ram
    instance.cores = flavor.cores
    instance.flavor_name = flavor.name
    instance.save(update_fields=['ram', 'cores', 'flavor_name'])

    server_id = instance.backend_id
    flavor_id = flavor.backend_id

    chain(
        nova_server_resize.s(client.session, server_id, flavor_id),
        nova_wait_for_server_status.s(server_id, 'VERIFY_RESIZE'),
        nova_server_resize_confirm.s(server_id),
        nova_wait_for_server_status.s(server_id, 'SHUTOFF'),
    ).apply_async(
        link=flavor_change_succeeded.si(instance_uuid, flavor_uuid),
        link_error=flavor_change_failed.s(instance_uuid, flavor_uuid),
    )


@shared_task
@transition(Instance, 'set_resized')
def flavor_change_succeeded(instance_uuid, flavor_uuid, transition_entity=None):
    instance = transition_entity
    flavor = Flavor.objects.get(
        settings=instance.service_project_link.service.settings,
        uuid=flavor_uuid)

    logger.info('Successfully changed flavor of an instance %s', instance.uuid)
    event_logger.openstack_flavor.info(
        'Virtual machine {resource_name} flavor has been changed to {flavor_name}.',
        event_type='resource_flavor_change_succeeded',
        event_context={'resource': instance, 'flavor': flavor}
    )


@shared_task
@transition(Instance, 'set_erred')
@save_error_message_from_task
def flavor_change_failed(task_uuid, instance_uuid, flavor_uuid, transition_entity=None):
    instance = transition_entity
    flavor = Flavor.objects.get(
        settings=instance.service_project_link.service.settings,
        uuid=flavor_uuid)

    logger.exception('Failed to change flavor of an instance %s', instance.uuid)
    event_logger.openstack_flavor.error(
        'Virtual machine {resource_name} flavor change has failed.',
        event_type='resource_flavor_change_failed',
        event_context={'resource': instance, 'flavor': flavor}
    )
