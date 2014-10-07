from __future__ import unicode_literals
from datetime import datetime, timedelta

from django.db import models, IntegrityError
from django.utils import timezone
from django.utils.encoding import python_2_unicode_compatible
from django.contrib.contenttypes import models as ct_models
from django.contrib.contenttypes import generic as ct_generic

from django_fsm import FSMField, transition
from croniter.croniter import croniter

from nodeconductor.core import models as core_models
from nodeconductor.core import fields as core_fields
from nodeconductor.backup import tasks


def get_backupable_models():
    """
        Looks throught all project apps and finds non-abstract models,
        that implement BackupableMixin
    """
    for model in models.get_models():
        if isinstance(model, BackupableMixin):
            yield model


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

    def _update_next_trigger_at(self):
        """
        Defines next backup creation time
        """
        base_time = timezone.now()
        self.next_trigger_at = croniter(self.schedule, base_time).get_next(datetime)

    def _create_backup(self):
        """
        Creates new backup based on schedule and starts backup process
        """
        backup = Backup.objects.create(
            backup_schedule=self,
            backup_source=self.backup_source,
            kept_until=timezone.now() + timedelta(days=self.maximal_number_of_backups))
        backup.start_backup()
        return backup

    def execute(self):
        """
        Creates new backup and deletes existed if maximal_number_of_backups were riched
        """
        self._create_backup()
        backups_count = self.backups.exclude(state__in=[Backup.States.DELETING, Backup.States.DELETED]).count()
        extra_backups_count = backups_count - self.maximal_number_of_backups
        if extra_backups_count > 0:
            for backup in self.backups.order_by('created_at')[:extra_backups_count]:
                backup.start_delete()
        self._update_next_trigger_at()
        self.save()

    def save(self, *args, **kwargs):
        """
            Updates next_trigger_at field if:
             - instance become active
             - instance.schedule changed
             - instance is new
        """
        try:
            prev_instance = BackupSchedule.objects.get(pk=self.pk)
            if (not prev_instance.is_active and self.is_active or
                    self.schedule != prev_instance.schedule):
                self._update_next_trigger_at()
        except BackupSchedule.DoesNotExist:
            self._update_next_trigger_at()
        return super(BackupSchedule, self).save(*args, **kwargs)

    @classmethod
    def execute_all_schedules(self):
        """
        Deletes all expired backups and creates new backups if schedules next_trigger_at time passed
        """
        for backup in Backup.objects.filter(kept_until__lt=timezone.now()):
            backup.start_delete()
        for schedule in BackupSchedule.objects.filter(is_active=True, next_trigger_at__lt=timezone.now()):
            schedule.execute()


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
    result_id = models.CharField(max_length=63, null=True)

    def __str__(self):
        return '%(uuid)s backup of %(object)s' % {
            'uuid': self.uuid,
            'object': self.backup_source,
        }

    @transition(field=state, source=States.READY, on_error=States.ERRED)
    def start_backup(self):
        """
        Create a new backup of the latest state.
        """
        result = tasks.backup_task.delay(self.backup_source)
        self.result_id = result.id
        self.state = self.States.BACKUPING
        self.__save()

    @transition(field=state, source=States.BACKUPING, on_error=States.ERRED)
    def verify_backup(self):
        """
        Verifies new backup creation
        """
        result = tasks.backup_task.AsyncResult(self.result_id)
        print result
        if result.ready():
            self.state = self.States.READY
            self.__save()

    @transition(field=state, source=States.READY, on_error=States.ERRED)
    def start_restore(self, replace_original=False):
        """
        Restore a defined backup.
        If 'replace_original' is True, should attempt to rewrite the latest state. False by default.
        """
        result = tasks.restore_task.delay(self.backup_source)
        self.result_id = result.id
        self.state = self.States.RESTORING
        self.__save()

    @transition(field=state, source=States.RESTORING, on_error=States.ERRED)
    def verify_restore(self):
        """
        Verify restoration of backup instance
        """
        result = tasks.restore_task.AsyncResult(self.result_id)
        if result.ready():
            self.state = self.States.READY
            self.__save()

    @transition(field=state, source=States.READY, on_error=States.ERRED)
    def start_delete(self):
        """
        Delete a specified backup instance
        """
        result = tasks.delete_task.delay(self.backup_source)
        self.result_id = result.id
        self.state = self.States.DELETING
        self.__save()

    @transition(field=state, source=States.DELETING, on_error=States.ERRED)
    def verify_delete(self):
        """
        Verify deletion of a backup instance.
        """
        result = tasks.delete_task.AsyncResult(self.result_id)
        if result.ready():
            self.state = self.States.DELETED
            self.__save()

    def __save(self, *args, **kwargs):
        return super(Backup, self).save(*args, **kwargs)

    def save(self, *args, **kwargs):
        """
            Raies IntegrityError if backup is modified
        """
        if self.pk is not None:
            raise IntegrityError('Backup is unmodified')
        else:
            return super(Backup, self).save(*args, **kwargs)


class BackupableMixin(models.Model):
    """
    Mixin to mark model that model can be backed up and require model to implement
    a get_backup_strategy() function for Model-specific backup approach.
    """
    class Meta(object):
        abstract = True

    backups = ct_generic.GenericRelation('Backup')
    backup_schedules = ct_generic.GenericRelation('BackupSchedule')

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
