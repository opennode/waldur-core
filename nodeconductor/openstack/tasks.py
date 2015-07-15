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


@shared_task(is_heavy_task=True)
@transition(Instance, 'begin_provisioning')
def provision_instance(instance_uuid, transition_entity=None, **kwargs):
    instance = transition_entity
    with throttle(key=instance.service_project_link.service.settings.backend_url):
        backend = instance.get_backend()
        backend.provision_instance(instance, **kwargs)


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
