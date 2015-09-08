import logging

from celery import shared_task

from nodeconductor.core.tasks import transition, throttle
from nodeconductor.openstack.backend import OpenStackBackendError
from nodeconductor.openstack.models import OpenStackServiceProjectLink, Instance, SecurityGroup


logger = logging.getLogger(__name__)


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


@shared_task(name='nodeconductor.openstack.sync_instance_security_groups')
def sync_instance_security_groups(instance_uuid):
    instance = Instance.objects.get(uuid=instance_uuid)
    backend = instance.get_backend()
    backend.sync_instance_security_groups(instance)


@shared_task(name='nodeconductor.openstack.sync_security_group')
@transition(SecurityGroup, 'begin_syncing')
def sync_security_group(security_group_uuid, action, transition_entity=None):
    security_group = transition_entity
    backend = security_group.service_project_link.get_backend()

    @transition(SecurityGroup, 'set_in_sync')
    def succeeded(security_group_uuid, transition_entity=None):
        pass

    @transition(SecurityGroup, 'set_erred')
    def failed(security_group_uuid, transition_entity=None):
        pass

    try:
        func = getattr(backend, '%s_security_group' % action)
        func(security_group)
    except:
        failed(security_group_uuid)
        raise
    else:
        if action == 'delete':
            security_group.delete()
        else:
            succeeded(security_group_uuid)


@shared_task(name='nodeconductor.openstack.sync_external_network')
def sync_external_network(service_project_link_str, action, data=()):
    service_project_link = next(OpenStackServiceProjectLink.from_string(service_project_link_str))
    backend = service_project_link.get_backend()

    try:
        func = getattr(backend, '%s_external_network' % action)
        func(service_project_link, **data)
    except OpenStackBackendError:
        logger.warning(
            "Failed to %s external network for service project link %s.",
            action, service_project_link_str)


@shared_task(name='nodeconductor.openstack.allocate_floating_ip')
def allocate_floating_ip(service_project_link_str):
    service_project_link = next(OpenStackServiceProjectLink.from_string(service_project_link_str))
    backend = service_project_link.get_backend()

    try:
        backend.allocate_floating_ip_address(service_project_link)
    except OpenStackBackendError:
        logger.warning(
            "Failed to allocate floating IP for service project link %s.",
            service_project_link_str)


@shared_task
def assign_floating_ip(instance_uuid, floating_ip_uuid):
    instance = Instance.objects.get(uuid=instance_uuid)
    floating_ip = instance.service_project_link.floating_ips.get(uuid=floating_ip_uuid)
    backend = instance.cloud.get_backend()

    try:
        backend.assign_floating_ip_to_instance(instance, floating_ip)
    except OpenStackBackendError:
        logger.warning("Failed to assign floating IP to the instance with id %s.", instance_uuid)


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
