import logging

from celery import shared_task
from django.utils import timezone

from nodeconductor.core.tasks import transition
from nodeconductor.openstack.backup import BackupError
from nodeconductor.openstack.models import BackupSchedule, Backup
from nodeconductor.structure.log import event_logger

logger = logging.getLogger(__name__)


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
def backup_start_create(backup_uuid, transition_entity=None):
    backup_create.apply_async(
        args=(backup_uuid,),
        link=backup_creation_complete.si(backup_uuid),
        link_error=backup_failed.si(backup_uuid))


@shared_task(name='nodeconductor.openstack.backup_start_delete')
def backup_start_delete(backup_uuid, transition_entity=None):
    backup_delete.apply_async(
        args=(backup_uuid,),
        link=backup_deletion_complete.si(backup_uuid),
        link_error=backup_failed.si(backup_uuid))


@shared_task(name='nodeconductor.openstack.backup_start_restore')
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
