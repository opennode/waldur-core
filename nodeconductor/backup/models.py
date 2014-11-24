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
from nodeconductor.backup import managers


class BackupSourceAbstractModel(models.Model):
    """
    Abstract model with generic key to backup source
    """
    # reference to the backed up object
    content_type = models.ForeignKey(ct_models.ContentType)
    object_id = models.PositiveIntegerField()
    backup_source = ct_generic.GenericForeignKey('content_type', 'object_id')

    class Meta(object):
        abstract = True

    def user_has_perm_for_backup_source(self, user):
        permission_name = '%s.add_%s' % (self.content_type.app_label, self.content_type.model)
        return user.has_perm(permission_name, self.backup_source)


@python_2_unicode_compatible
class BackupSchedule(core_models.UuidMixin,
                     core_models.DescribableMixin,
                     BackupSourceAbstractModel):
    """
    Model representing a backup schedule for a generic object.
    """
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
            kept_until=timezone.now() + timedelta(days=self.retention_time),
            description='scheduled backup')
        backup.start_backup()
        return backup

    def _delete_extra_backups(self):
        """
        Deletes oldest existing backups if maximal_number_of_backups was reached
        """
        exclude_states = (Backup.States.DELETING, Backup.States.DELETED, Backup.States.ERRED)
        backups_count = self.backups.exclude(state__in=exclude_states).count()
        extra_backups_count = backups_count - self.maximal_number_of_backups
        if extra_backups_count > 0:
            for backup in self.backups.order_by('created_at')[:extra_backups_count]:
                backup.start_deletion()

    def execute(self):
        """
        Creates new backup, deletes existing if maximal_number_of_backups was
        reached, calculates new next_trigger_at time.
        """
        self._create_backup()
        self._delete_extra_backups()
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
        except BackupSchedule.DoesNotExist:
            prev_instance = None

        super(BackupSchedule, self).save(*args, **kwargs)

        if prev_instance is None or (not prev_instance.is_active and self.is_active or
                                     self.schedule != prev_instance.schedule):
            self._update_next_trigger_at()


@python_2_unicode_compatible
class Backup(core_models.UuidMixin,
             core_models.DescribableMixin,
             BackupSourceAbstractModel):
    """
    Model representing a single instance of a backup.
    """
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
        BACKING_UP = 'p'
        RESTORING = 'r'
        DELETING = 'l'
        ERRED = 'e'
        DELETED = 'x'

    STATE_CHOICES = (
        (States.READY, 'Ready'),
        (States.BACKING_UP, 'Backing up'),
        (States.RESTORING, 'Restoring'),
        (States.DELETING, 'Deleting'),
        (States.ERRED, 'Erred'),
        (States.DELETED, 'Deleted'),
    )

    state = FSMField(default=States.READY, max_length=1, choices=STATE_CHOICES)
    result_id = models.CharField(max_length=63, null=True)

    objects = managers.BackupManager()

    def __str__(self):
        return '%(uuid)s backup of %(object)s' % {
            'uuid': self.uuid,
            'object': self.backup_source,
        }

    def start_backup(self):
        """
        Starts celery backup task
        """
        from nodeconductor.backup import tasks

        self._starting_backup()
        result = tasks.process_backup_task.delay(self.uuid.hex)
        self.result_id = result.id
        self.__save()

    def start_restoration(self, replace_original=False):
        """
        Starts backup restoration task.
        If 'replace_original' is True, should attempt to rewrite the latest state. False by default.
        """
        from nodeconductor.backup import tasks

        self._starting_restoration()
        result = tasks.restoration_task.delay(self.uuid.hex, replace_original=False)
        self.result_id = result.id
        self.__save()

    def start_deletion(self):
        """
        Starts backup deletion task
        """
        from nodeconductor.backup import tasks

        self._starting_deletion()
        result = tasks.deletion_task.delay(self.uuid.hex)
        self.result_id = result.id
        self.__save()

    def poll_current_state(self):
        """
        Checks status of the backup task. Updates the backup state on task completion.
        """
        from nodeconductor.backup import tasks

        if self.state == self.States.BACKING_UP:
            self._check_task_result(tasks.backup_task, self._confirm_backup)
        elif self.state == self.States.RESTORING:
            self._check_task_result(tasks.restoration_task, self._confirm_restoration)
        elif self.state == self.States.DELETING:
            self._check_task_result(tasks.deletion_task, self._confirm_deletion)
        self.__save()

    def _check_task_result(self, task, confirm_function):
        """
        Gets task result by its id. If it is ready - executes confirm function
        """
        result = task.AsyncResult(self.result_id)
        if result is None:
            self._erred()
        elif result.ready():
            confirm_function()

    @transition(field=state, source=States.READY, target=States.BACKING_UP)
    def _starting_backup(self):
        pass

    @transition(field=state, source=States.BACKING_UP, target=States.READY)
    def _confirm_backup(self):
        pass

    @transition(field=state, source=States.READY, target=States.RESTORING)
    def _starting_restoration(self):
        pass

    @transition(field=state, source=States.RESTORING, target=States.READY)
    def _confirm_restoration(self):
        pass

    @transition(field=state, source=States.READY, target=States.DELETING)
    def _starting_deletion(self):
        pass

    @transition(field=state, source=States.DELETING, target=States.DELETED)
    def _confirm_deletion(self):
        pass

    @transition(field=state, source='*', target=States.ERRED)
    def _erred(self):
        pass

    def __save(self, *args, **kwargs):
        return super(Backup, self).save(*args, **kwargs)

    def save(self, *args, **kwargs):
        """
        Raises IntegrityError if backup is modified
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
    def restore(self, replace_original):
        raise NotImplementedError(
            'Implement restore() that would perform backup of a model.')

    @classmethod
    def delete(self):
        raise NotImplementedError(
            'Implement delete() that would perform backup of a model.')
