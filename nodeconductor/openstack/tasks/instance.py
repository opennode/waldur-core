import logging

from celery import shared_task

from nodeconductor.core.tasks import save_error_message, transition, throttle
from nodeconductor.openstack.models import Instance, FloatingIP, Tenant


logger = logging.getLogger(__name__)


@shared_task(name='nodeconductor.openstack.provision')
def provision(instance_uuid, **kwargs):
    instance = Instance.objects.get(uuid=instance_uuid)
    spl = instance.service_project_link
    tenant = spl.tenant

    if tenant is None:
        from nodeconductor.openstack import executors

        tenant = spl.create_tenant()
        executors.TenantCreateExecutor.execute(tenant, async=False)
        tenant.refresh_from_db()
        if tenant.state != Tenant.States.OK:
            instance.set_erred()
            instance.error_message = 'Tenant %s (PK: %s) creation failed.' % (tenant, tenant.pk)
            instance.save()
            return

    provision_instance.apply_async(
        args=(instance_uuid,),
        kwargs=kwargs,
        link=set_online.si(instance_uuid),
        link_error=set_erred.si(instance_uuid)
    )


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


@shared_task(is_heavy_task=True)
@transition(Instance, 'begin_provisioning')
@save_error_message
def provision_instance(instance_uuid, transition_entity=None, **kwargs):
    instance = transition_entity
    with throttle(key=instance.service_project_link.service.settings.backend_url):
        backend = instance.get_backend()
        backend.provision_instance(instance, **kwargs)


@shared_task
@transition(Instance, 'begin_starting')
@save_error_message
def start_instance(instance_uuid, transition_entity=None):
    instance = transition_entity
    backend = instance.get_backend()
    backend.start_instance(instance)


@shared_task
@transition(Instance, 'begin_stopping')
@save_error_message
def stop_instance(instance_uuid, transition_entity=None):
    instance = transition_entity
    backend = instance.get_backend()
    backend.stop_instance(instance)


@shared_task
@transition(Instance, 'begin_restarting')
@save_error_message
def restart_instance(instance_uuid, transition_entity=None):
    instance = transition_entity
    backend = instance.get_backend()
    backend.restart_instance(instance)


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
