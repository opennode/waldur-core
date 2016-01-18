import logging
import sys

from celery import shared_task, chain
from django.utils import six, timezone

from nodeconductor.core.tasks import save_error_message, transition, throttle
from nodeconductor.core.models import SynchronizationStates
from nodeconductor.openstack.backend import OpenStackBackendError
from nodeconductor.openstack.backup import BackupError
from nodeconductor.openstack.models import OpenStackServiceProjectLink, Instance, Flavor, FloatingIP, SecurityGroup
from nodeconductor.openstack.models import BackupSchedule, Backup
from nodeconductor.structure.models import ServiceSettings
from nodeconductor.structure.log import event_logger
from nodeconductor.structure.tasks import (
    begin_syncing_service_project_links, sync_service_project_link_succeeded, sync_service_project_link_failed)


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
            link=chain(sync_service_project_link_succeeded.si(spl.to_string()),
                       provision.si(instance_uuid, **kwargs)),
            link_error=chain(sync_service_project_link_failed.si(spl.to_string()),
                             set_erred.si(instance_uuid)),
        )
    else:
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


@shared_task(name='nodeconductor.openstack.remove_tenant')
def remove_tenant(settings_uuid, tenant_id):
    settings = ServiceSettings.objects.get(uuid=settings_uuid)
    backend = settings.get_backend(tenant_id=tenant_id)
    backend.cleanup(dryrun=False)


@shared_task(name='nodeconductor.openstack.resize_flavor')
def resize_flavor(instance_uuid, flavor_uuid):
    resize_instance_flavor.apply_async(
        args=(instance_uuid, flavor_uuid),
        link=flavor_change_succeeded.si(instance_uuid, flavor_uuid),
        link_error=flavor_change_failed.si(instance_uuid, flavor_uuid))


@shared_task(name='nodeconductor.openstack.extend_disk')
def extend_disk(instance_uuid, disk_size):
    extend_instance_disk.apply_async(
        args=(instance_uuid, disk_size),
        link=disk_extension_succeeded.si(instance_uuid, disk_size),
        link_error=disk_extension_failed.si(instance_uuid, disk_size))


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
@transition(Instance, 'begin_resizing')
@save_error_message
def extend_instance_disk(instance_uuid, disk_size, transition_entity=None):
    instance = transition_entity
    instance.data_volume_size = disk_size
    instance.save(update_fields=['data_volume_size'])

    backend = instance.get_backend()
    backend.extend_disk(instance)


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


@shared_task
@transition(Instance, 'set_resized')
def disk_extension_succeeded(instance_uuid, disk_size, transition_entity=None):
    instance = transition_entity
    event_logger.instance_flavor.info(
        'Virtual machine {resource_name} disk has been extended to {volume_size}.',
        event_type='resource_volume_extension_succeeded',
        event_context={'resource': instance, 'volume_size': disk_size}
    )


@shared_task
@transition(Instance, 'set_erred')
def disk_extension_failed(instance_uuid, disk_size, transition_entity=None):
    instance = transition_entity
    event_logger.instance_flavor.info(
        'Virtual machine {resource_name} disk has been failed.',
        event_type='resource_volume_extension_failed',
        event_context={'resource': instance, 'volume_size': disk_size}
    )


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


# Security-group related methods
# XXX: copy-paste from iaas.tasks.security_groups
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


@shared_task(name='nodeconductor.openstack.schedule_backups')
def schedule_backups():
    for schedule in BackupSchedule.objects.filter(is_active=True, next_trigger_at__lt=timezone.now()):
        backend = schedule.get_backend()
        backend.execute()


@shared_task(name='nodeconductor.openstack.delete_expired_backups')
def delete_expired_backups():
    for backup in Backup.objects.filter(kept_until__lt=timezone.now(), state=Backup.States.READY):
        backend = backup.get_backend()
        backend.start_deletion()


@shared_task(name='nodeconductor.openstack.backup_start_create')
@transition(Backup, 'starting_backup')
def backup_start_create(backup_uuid, transition_entity=None):
    backup_create.apply_async(
        args=(backup_uuid,),
        link=backup_creation_complete.si(backup_uuid),
        link_error=backup_failed.si(backup_uuid))


@shared_task(name='nodeconductor.openstack.backup_start_delete')
@transition(Backup, 'starting_deletion')
def backup_start_delete(backup_uuid, transition_entity=None):
    backup_delete.apply_async(
        args=(backup_uuid,),
        link=backup_deletion_complete.si(backup_uuid),
        link_error=backup_failed.si(backup_uuid))


@shared_task(name='nodeconductor.openstack.backup_start_restore')
@transition(Backup, 'starting_restoration')
def backup_start_restore(backup_uuid, instance_uuid, user_input, snapshot_ids, transition_entity=None):
    backup_restore.apply_async(
        args=(backup_uuid, instance_uuid, user_input, snapshot_ids),
        link=backup_restoration_complete.si(backup_uuid),
        link_error=backup_failed.si(backup_uuid))


@shared_task
def backup_create(backup_uuid):
    backup = Backup.objects.get(uuid=backup_uuid)

    logger.debug('About to perform backup for instance: %s', backup.instance)
    event_logger.openstack_backup.info(
        'Backup for {resource_name} has been scheduled.',
        event_type='resource_backup_creation_scheduled',
        event_context={'resource': backup.instance})

    try:
        backend = backup.get_backend()
        backup.metadata = backend.create()
        backup.save()
    except BackupError:
        logger.exception('Failed to perform backup for instance: %s', backup.instance)
        schedule = backup.backup_schedule
        if schedule:
            schedule.is_active = False
            schedule.save()

            event_logger.openstack_backup.info(
                'Backup schedule for {resource_name} has been deactivated.',
                event_type='resource_backup_schedule_deactivated',
                event_context={'resource': backup.instance})

        event_logger.openstack_backup.error(
            'Backup creation for {resource_name} has failed.',
            event_type='resource_backup_creation_failed',
            event_context={'resource': backup.instance})

    else:
        logger.info('Successfully performed backup for instance: %s', backup.instance)
        event_logger.openstack_backup.info(
            'Backup for {resource_name} has been created.',
            event_type='resource_backup_creation_succeeded',
            event_context={'resource': backup.instance})


@shared_task
def backup_delete(backup_uuid):
    backup = Backup.objects.get(uuid=backup_uuid)

    logger.debug('About to delete backup for instance: %s', backup.instance)
    event_logger.openstack_backup.info(
        'Backup deletion for {resource_name} has been scheduled.',
        event_type='resource_backup_deletion_scheduled',
        event_context={'resource': backup.instance})

    try:
        backend = backup.get_backend()
        backend.delete()
    except BackupError:
        logger.exception('Failed to delete backup for instance: %s', backup.instance)
        event_logger.openstack_backup.error(
            'Backup deletion for {resource_name} has failed.',
            event_type='resource_backup_deletion_failed',
            event_context={'resource': backup.instance})
    else:
        logger.info('Successfully deleted backup for instance: %s', backup.instance)
        event_logger.openstack_backup.info(
            'Backup for {resource_name} has been deleted.',
            event_type='resource_backup_deletion_succeeded',
            event_context={'resource': backup.instance})


@shared_task
def backup_restore(backup_uuid, instance_uuid, user_input, snapshot_ids):
    backup = Backup.objects.get(uuid=backup_uuid)

    logger.debug('About to restore backup for instance: %s', backup.instance)
    event_logger.openstack_backup.info(
        'Backup restoration for {resource_name} has been scheduled.',
        event_type='resource_backup_restoration_scheduled',
        event_context={'resource': backup.instance})

    try:
        backend = backup.get_backend()
        backend.restore(instance_uuid, user_input, snapshot_ids)
    except BackupError:
        logger.exception('Failed to restore backup for instance: %s', backup.instance)
        event_logger.openstack_backup.error(
            'Backup restoration for {resource_name} has failed.',
            event_type='resource_backup_restoration_failed',
            event_context={'resource': backup.instance})
    else:
        logger.info('Successfully restored backup for instance: %s', backup.instance)
        event_logger.openstack_backup.info(
            'Backup for {resource_name} has been restored.',
            event_type='resource_backup_restoration_succeeded',
            event_context={'resource': backup.instance})


@shared_task
@transition(Backup, 'confirm_backup')
def backup_creation_complete(backup_uuid, transition_entity=None):
    pass


@shared_task
@transition(Backup, 'confirm_deletion')
def backup_deletion_complete(backup_uuid, transition_entity=None):
    pass


@shared_task
@transition(Backup, 'confirm_restoration')
def backup_restoration_complete(backup_uuid, transition_entity=None):
    pass


@shared_task
@transition(Backup, 'set_erred')
def backup_failed(backup_uuid, transition_entity=None):
    pass


@shared_task
def openstack_update_tenant_name(service_project_link_str):
    service_project_link = next(OpenStackServiceProjectLink.from_string(service_project_link_str))
    backend = service_project_link.get_backend()
    backend.update_tenant_name(service_project_link)
