import logging

from celery import shared_task

from nodeconductor.core.tasks import save_error_message, transition
from nodeconductor.openstack.models import Instance, Flavor
from nodeconductor.structure.log import event_logger

logger = logging.getLogger(__name__)


@shared_task(name='nodeconductor.openstack.resize_flavor')
def resize_flavor(instance_uuid, flavor_uuid):
    resize_instance_flavor.apply_async(
        args=(instance_uuid, flavor_uuid),
        link=flavor_change_succeeded.si(instance_uuid, flavor_uuid),
        link_error=flavor_change_failed.si(instance_uuid, flavor_uuid))


@shared_task
@transition(Instance, 'begin_resizing')
@save_error_message
def resize_instance_flavor(instance_uuid, flavor_uuid, transition_entity=None):
    instance = transition_entity
    flavor = Flavor.objects.get(
        settings=instance.service_project_link.service.settings,
        uuid=flavor_uuid)

    instance.ram = flavor.ram
    instance.cores = flavor.cores
    instance.flavor_name = flavor.name
    instance.save(update_fields=['ram', 'cores', 'flavor_name'])

    backend = instance.get_backend()
    backend.update_flavor(instance, flavor)


@shared_task
@transition(Instance, 'set_resized')
def flavor_change_succeeded(instance_uuid, flavor_uuid, transition_entity=None):
    instance = transition_entity
    flavor = Flavor.objects.get(
        settings=instance.service_project_link.service.settings,
        uuid=flavor_uuid)

    logger.info('Successfully changed flavor of an instance %s', instance.uuid)
    event_logger.instance_flavor.info(
        'Virtual machine {resource_name} flavor has been changed to {flavor_name}.',
        event_type='resource_flavor_change_succeeded',
        event_context={'resource': instance, 'flavor': flavor}
    )


@shared_task
@transition(Instance, 'set_erred')
def flavor_change_failed(instance_uuid, flavor_uuid, transition_entity=None):
    instance = transition_entity
    flavor = Flavor.objects.get(
        settings=instance.service_project_link.service.settings,
        uuid=flavor_uuid)

    logger.exception('Failed to change flavor of an instance %s', instance.uuid)
    event_logger.instance_flavor.error(
        'Virtual machine {resource_name} flavor change has failed.',
        event_type='resource_flavor_change_failed',
        event_context={'resource': instance, 'flavor': flavor}
    )
