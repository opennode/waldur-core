from __future__ import unicode_literals
from datetime import datetime

from django.db import models
from django.utils import timezone
from django.utils.encoding import python_2_unicode_compatible
from django.contrib.contenttypes import models as ct_models
from django.contrib.contenttypes import generic as ct_generic
from django.db.models import signals

from django_fsm import FSMField, transition
from croniter.croniter import croniter

from nodeconductor.core import models as core_models
from nodeconductor.core import fields as core_fields


@python_2_unicode_compatible
class BackupSchedule(core_models.UuidMixin,
                     core_models.DescribableMixin,
                     models.Model):
    """
        Model representing a backup schedule for a generic object.
    """
    # reference to the backed up object
    content_type = models.ForeignKey(ct_models.ContentType)
    object_id = models.PositiveIntegerField()
    backup_source = ct_generic.GenericForeignKey('content_type', 'object_id')

    # backup specific settings
    retention_time = models.PositiveIntegerField(help_text='Retention time in days')
    maximal_number_of_backups = models.PositiveSmallIntegerField()
    schedule = core_fields.CronScheduleField(max_length=15)
    next_trigger_at = models.DateTimeField(null=True)
    is_active = models.BooleanField(default=False)

    def __str__(self):
        return '%(uuid)s BackupSchedule of %(object)s' % {
            'uuid': self.uuid,
            'object': self.backup_source,
            'schedule': self.schedule,
        }


def update_next_trigger_at(sender, instance, **kwargs):
    prev_instance = BackupSchedule.objects.get(pk=instance.pk)
    if not prev_instance.is_active and instance.is_active:
        base_time = timezone.now()
        instance.next_trigger_at = datetime.fromtimestamp(croniter(instance.schedule, base_time).get_next())

    # TODO: check if schedule has changed and schedule is_active => lookup next scheduled Backup and cancel it, reschedule
    # TODO: check if schedule has been deactivated => lookup next scheduled Backup and cancel it


signals.pre_save.connect(update_next_trigger_at,
                          sender=BackupSchedule,
                          weak=False,
                          dispatch_uid='backup.backup_schedule_calculation')

@python_2_unicode_compatible
class Backup(core_models.UuidMixin,
             core_models.DescribableMixin,
             models.Model):
    """
        Model representing a single instance of a backup.
    """

    # TODO: check if possible to prohibit updates
    content_type = models.ForeignKey(ct_models.ContentType)
    object_id = models.PositiveIntegerField()
    backup_source = ct_generic.GenericForeignKey('content_type', 'object_id')

    backup_schedule = models.ForeignKey(BackupSchedule, blank=True, null=True,
                                        on_delete=models.SET_NULL,
                                        related_name='backups')
    kept_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Guaranteed time of backup retention. If null - keep forever.')

    created_at = models.DateTimeField(auto_now_add=True)

    class States(object):
        READY = 'd'
        BACKUPING = 'p'
        RESTORING = 'r'
        DELETING = 'l'
        ERRED = 'e'
        DELETED = 'x'

    STATE_CHOICES = (
        (States.READY, 'Ready'),
        (States.BACKUPING, 'Backuping'),
        (States.RESTORING, 'Restoring'),
        (States.DELETING, 'Deleting'),
        (States.ERRED, 'Erred'),
        (States.DELETED, 'Deleted'),
    )

    state = FSMField(default=States.READY, max_length=1, choices=STATE_CHOICES)

    @transition(field=state, source=States.READY, target=States.BACKUPING, on_error=States.ERRED)
    def start_backup(self):
        """
        Create a new backup of the latest state.
        """
        raise NotImplementedError(
            'Implement backup() for backup strategy implementation')

    @transition(field=state, source=States.BACKUPING, target=States.READY, on_error=States.ERRED)
    def verify_backup(self):
        """
        Create a new backup of the latest state.
        """
        raise NotImplementedError(
            'Implement backup() for backup strategy implementation')

    @transition(field=state, source=States.READY, target=States.RESTORING, on_error=States.ERRED)
    def start_restore(self, backup, replace_original=False):
        """
        Restore a defined backup.
        If 'replace_original' is True, should attempt to rewrite the latest state. False by default.
        """
        raise NotImplementedError(
            'Implement restore() for backup strategy implementation')

    @transition(field=state, source=States.RESTORING, target=States.READY, on_error=States.ERRED)
    def verify_restore(self, backup):
        """
        Restore a defined backup.
        If 'replace_original' is True, should attempt to rewrite the latest state. False by default.
        """
        raise NotImplementedError(
            'Implement restore() for backup strategy implementation')

    @transition(field=state, source=States.READY, target=States.DELETING, on_error=States.ERRED)
    def start_delete(self, backup):
        """
        Delete a specified backup instance
        """
        raise NotImplementedError(
            'Implement backup() for backup strategy implementation')

    @transition(field=state, source=States.DELETING, target=States.READY, on_error=States.ERRED)
    def verify_delete(self, backup):
        """
        Verify deletion of a backup instance.
        """
        raise NotImplementedError(
            'Implement backup() for backup strategy implementation')


    def __str__(self):
        return '%(uuid)s backup of %(object)s' % {
            'uuid': self.uuid,
            'object': self.backup_source,
        }


class BackupableMixin(models.Model):
    """
    Mixin to mark model that model can be backed up and require model to implement
    a get_backup_strategy() function for Model-specific backup approach.
    """
    class Meta(object):
        abstract = True

    backups = ct_generic.GenericRelation(Backup)
    backup_schedules = ct_generic.GenericRelation(BackupSchedule)

    def get_backup_strategy(self):
        raise NotImplementedError(
            'Implement get_backup_strategy() that would return a method for backing up instance of a model.')


class BackupStrategy(object):
    """
    A parent class for the model-specific backup strategies.
    """

    @classmethod
    def backup(self):
        raise NotImplementedError(
            'Implement backup() that would perform backup of a model.')

    @classmethod
    def restore(self):
        raise NotImplementedError(
            'Implement restore() that would perform backup of a model.')

    @classmethod
    def delete(self):
        raise NotImplementedError(
            'Implement delete() that would perform backup of a model.')
