import logging

from celery import shared_task

from nodeconductor.core.tasks import save_error_message, transition
from nodeconductor.openstack.models import Instance
from nodeconductor.structure.log import event_logger

logger = logging.getLogger(__name__)


@shared_task(name='nodeconductor.openstack.extend_disk')
def extend_disk(instance_uuid, disk_size):
    extend_instance_disk.apply_async(
        args=(instance_uuid, disk_size),
        link=disk_extension_succeeded.si(instance_uuid, disk_size),
        link_error=disk_extension_failed.si(instance_uuid, disk_size))


@shared_task
@transition(Instance, 'begin_resizing')
@save_error_message
def extend_instance_disk(instance_uuid, disk_size, transition_entity=None):
    instance = transition_entity
    instance.data_volume_size = disk_size
    instance.save(update_fields=['data_volume_size'])

    backend = instance.get_backend()
    backend.extend_disk(instance)


@shared_task
@transition(Instance, 'set_resized')
def disk_extension_succeeded(instance_uuid, disk_size, transition_entity=None):
    instance = transition_entity
    event_logger.openstack_volume.info(
        'Virtual machine {resource_name} disk has been extended to {volume_size}.',
        event_type='resource_volume_extension_succeeded',
        event_context={'resource': instance, 'volume_size': disk_size}
    )


@shared_task
@transition(Instance, 'set_erred')
def disk_extension_failed(instance_uuid, disk_size, transition_entity=None):
    instance = transition_entity
    event_logger.openstack_volume.info(
        'Virtual machine {resource_name} disk has been failed.',
        event_type='resource_volume_extension_failed',
        event_context={'resource': instance, 'volume_size': disk_size}
    )
