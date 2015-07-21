from celery import shared_task

from nodeconductor.core.tasks import transition, throttle
from nodeconductor.openstack.models import Instance


@shared_task(name='nodeconductor.openstack.provision')
def provision(instance_uuid, **kwargs):
    provision_instance.apply_async(
        args=(instance_uuid,),
        kwargs=kwargs,
        link=set_online.si(instance_uuid),
        link_error=set_erred.si(instance_uuid))


@shared_task(name='nodeconductor.openstack.destroy')
@transition(Instance, 'begin_deleting')
def destroy(instance_uuid, transition_entity=None):
    instance = transition_entity
    try:
        backend = instance.get_backend()
        backend._old_backend.delete_instance(instance)
    except:
        set_erred(instance_uuid)
        raise
    else:
        instance.delete()


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


@shared_task(is_heavy_task=True)
@transition(Instance, 'begin_provisioning')
def provision_instance(instance_uuid, transition_entity=None, **kwargs):
    instance = transition_entity
    with throttle(key=instance.service_project_link.service.settings.backend_url):
        backend = instance.get_backend()
        backend.provision_instance(instance, **kwargs)


@shared_task
@transition(Instance, 'begin_starting')
def start_instance(instance_uuid, transition_entity=None):
    instance = transition_entity
    backend = instance.get_backend()
    backend._old_backend.start_instance(instance)


@shared_task
@transition(Instance, 'begin_stopping')
def stop_instance(instance_uuid, transition_entity=None):
    instance = transition_entity
    backend = instance.get_backend()
    backend._old_backend.stop_instance(instance)


@shared_task
@transition(Instance, 'begin_restarting')
def restart_instance(instance_uuid, transition_entity=None):
    instance = transition_entity
    backend = instance.get_backend()
    backend._old_backend.restart_instance(instance)


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
