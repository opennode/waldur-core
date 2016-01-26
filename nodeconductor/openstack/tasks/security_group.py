from celery import shared_task

from nodeconductor.core.tasks import transition
from nodeconductor.openstack.models import Instance, SecurityGroup


@shared_task(name='nodeconductor.openstack.sync_instance_security_groups')
def sync_instance_security_groups(instance_uuid):
    instance = Instance.objects.get(uuid=instance_uuid)
    backend = instance.get_backend()
    backend.sync_instance_security_groups(instance)


@shared_task(name='nodeconductor.openstack.create_security_group')
@transition(SecurityGroup, 'begin_syncing')
def create_security_group(security_group_uuid, transition_entity=None):
    security_group = transition_entity

    openstack_create_security_group.apply_async(
        args=(security_group.uuid.hex,),
        link=security_group_sync_succeeded.si(security_group_uuid),
        link_error=security_group_sync_failed.si(security_group_uuid),
    )


@shared_task(name='nodeconductor.openstack.update_security_group')
@transition(SecurityGroup, 'begin_syncing')
def update_security_group(security_group_uuid, transition_entity=None):
    security_group = transition_entity

    openstack_update_security_group.apply_async(
        args=(security_group.uuid.hex,),
        link=security_group_sync_succeeded.si(security_group_uuid),
        link_error=security_group_sync_failed.si(security_group_uuid),
    )


@shared_task(name='nodeconductor.openstack.delete_security_group')
@transition(SecurityGroup, 'begin_syncing')
def delete_security_group(security_group_uuid, transition_entity=None):
    security_group = transition_entity

    openstack_delete_security_group.apply_async(
        args=(security_group.uuid.hex,),
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
    SecurityGroup.objects.filter(uuid=security_group_uuid).delete()


@shared_task
def openstack_create_security_group(security_group_uuid):
    security_group = SecurityGroup.objects.get(uuid=security_group_uuid)
    backend = security_group.service_project_link.get_backend()
    backend.create_security_group(security_group)


@shared_task
def openstack_update_security_group(security_group_uuid):
    security_group = SecurityGroup.objects.get(uuid=security_group_uuid)
    backend = security_group.service_project_link.get_backend()
    backend.update_security_group(security_group)


@shared_task
def openstack_delete_security_group(security_group_uuid):
    security_group = SecurityGroup.objects.get(uuid=security_group_uuid)
    backend = security_group.service_project_link.get_backend()
    backend.delete_security_group(security_group)
