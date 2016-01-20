import logging
import sys

from celery import shared_task
from django.utils import six

from nodeconductor.core.tasks import save_error_message, transition, throttle
from nodeconductor.core.models import SynchronizationStates
from nodeconductor.openstack.models import Instance, FloatingIP
from nodeconductor.structure.models import ServiceSettings
from nodeconductor.structure.log import event_logger
from nodeconductor.structure.tasks import (
    begin_syncing_service_project_links,
    sync_service_project_link_succeeded,
    sync_service_project_link_failed)


logger = logging.getLogger(__name__)


@shared_task(name='nodeconductor.openstack.provision')
def provision(instance_uuid, **kwargs):
    instance = Instance.objects.get(uuid=instance_uuid)
    spl = instance.service_project_link
    if spl.state == SynchronizationStates.NEW:
        # Sync NEW SPL before instance provision
        spl.schedule_creating()
        spl.save()

        begin_syncing_service_project_links.apply_async(
            args=(spl.to_string(),),
            kwargs={'initial': True, 'transition_method': 'begin_creating'},
            link=set_spl_in_sync_and_start_provision.si(spl.to_string(), instance_uuid, **kwargs),
            link_error=set_spl_and_instance_as_erred.si(spl.to_string(), instance_uuid),
        )
    else:
        provision_instance.apply_async(
            args=(instance_uuid,),
            kwargs=kwargs,
            link=set_online.si(instance_uuid),
            link_error=set_erred.si(instance_uuid)
        )


@shared_task
def set_spl_in_sync_and_start_provision(service_project_link_str, instance_uuid, **kwargs):
    sync_service_project_link_succeeded(service_project_link_str)
    provision_instance.delay(instance_uuid, **kwargs)


@shared_task
def set_spl_and_instance_as_erred(service_project_link_str, instance_uuid):
    sync_service_project_link_failed(service_project_link_str)
    set_erred(instance_uuid)


@shared_task(name='nodeconductor.openstack.destroy')
def destroy(instance_uuid, force=False):
    if force:
        instance = Instance.objects.get(uuid=instance_uuid)

        FloatingIP.objects.filter(
            service_project_link=instance.service_project_link,
            address=instance.external_ips,
        ).update(status='DOWN')

        instance.delete()

        backend = instance.get_backend()
        backend.cleanup_instance(
            backend_id=instance.backend_id,
            external_ips=instance.external_ips,
            internal_ips=instance.internal_ips,
            system_volume_id=instance.system_volume_id,
            data_volume_id=instance.data_volume_id)

        return

    destroy_instance.apply_async(
        args=(instance_uuid,),
        link=delete.si(instance_uuid),
        link_error=set_erred.si(instance_uuid))


@shared_task(name='nodeconductor.openstack.start')
def start(instance_uuid):
    start_instance.apply_async(
        args=(instance_uuid,),
        link=set_online.si(instance_uuid),
        link_error=set_erred.si(instance_uuid))


@shared_task(name='nodeconductor.openstack.stop')
def stop(instance_uuid):
    stop_instance.apply_async(
        args=(instance_uuid,),
        link=set_offline.si(instance_uuid),
        link_error=set_erred.si(instance_uuid))


@shared_task(name='nodeconductor.openstack.restart')
def restart(instance_uuid):
    restart_instance.apply_async(
        args=(instance_uuid,),
        link=set_online.si(instance_uuid),
        link_error=set_erred.si(instance_uuid))


@shared_task(name='nodeconductor.openstack.remove_tenant')
def remove_tenant(settings_uuid, tenant_id):
    settings = ServiceSettings.objects.get(uuid=settings_uuid)
    backend = settings.get_backend(tenant_id=tenant_id)
    backend.cleanup(dryrun=False)


@shared_task(is_heavy_task=True)
@transition(Instance, 'begin_provisioning')
@save_error_message
def provision_instance(instance_uuid, transition_entity=None, **kwargs):
    instance = transition_entity
    with throttle(key=instance.service_project_link.service.settings.backend_url):
        backend = instance.get_backend()
        try:
            backend.provision_instance(instance, **kwargs)
        except:
            event_logger.resource.error(
                'Resource {resource_name} creation has failed.',
                event_type='resource_creation_failed',
                event_context={'resource': instance})
            six.reraise(*sys.exc_info())
        else:
            event_logger.resource.info(
                'Resource {resource_name} has been created.',
                event_type='resource_creation_succeeded',
                event_context={'resource': instance})


@shared_task
@transition(Instance, 'begin_starting')
@save_error_message
def start_instance(instance_uuid, transition_entity=None):
    instance = transition_entity
    backend = instance.get_backend()
    try:
        backend._old_backend.start_instance(instance)
    except:
        event_logger.resource.error(
            'Resource {resource_name} start has failed.',
            event_type='resource_start_failed',
            event_context={'resource': instance})
        six.reraise(*sys.exc_info())
    else:
        event_logger.resource.info(
            'Resource {resource_name} has been started.',
            event_type='resource_start_succeeded',
            event_context={'resource': instance})


@shared_task
@transition(Instance, 'begin_stopping')
@save_error_message
def stop_instance(instance_uuid, transition_entity=None):
    instance = transition_entity
    backend = instance.get_backend()
    try:
        backend._old_backend.stop_instance(instance)
    except:
        event_logger.resource.error(
            'Resource {resource_name} stop has failed.',
            event_type='resource_stop_failed',
            event_context={'resource': instance})
        six.reraise(*sys.exc_info())
    else:
        event_logger.resource.info(
            'Resource {resource_name} has been stopped.',
            event_type='resource_stop_succeeded',
            event_context={'resource': instance})


@shared_task
@transition(Instance, 'begin_restarting')
@save_error_message
def restart_instance(instance_uuid, transition_entity=None):
    instance = transition_entity
    backend = instance.get_backend()
    try:
        backend._old_backend.restart_instance(instance)
    except:
        event_logger.resource.error(
            'Resource {resource_name} restart has failed.',
            event_type='resource_restart_failed',
            event_context={'resource': instance})
        six.reraise(*sys.exc_info())
    else:
        event_logger.resource.info(
            'Resource {resource_name} has been restarted.',
            event_type='resource_restart_succeeded',
            event_context={'resource': instance})


@shared_task
@transition(Instance, 'begin_deleting')
@save_error_message
def destroy_instance(instance_uuid, transition_entity=None):
    instance = transition_entity
    backend = instance.get_backend()
    backend.delete_instance(instance)


@shared_task
@transition(Instance, 'set_online')
def set_online(instance_uuid, transition_entity=None):
    pass


@shared_task
@transition(Instance, 'set_offline')
def set_offline(instance_uuid, transition_entity=None):
    pass


@shared_task
@transition(Instance, 'set_erred')
def set_erred(instance_uuid, transition_entity=None):
    pass


@shared_task
def delete(instance_uuid):
    Instance.objects.get(uuid=instance_uuid).delete()
