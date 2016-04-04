from __future__ import unicode_literals

from datetime import datetime, timedelta
import logging
import pytz

from croniter.croniter import croniter
from django.db import models
from django.utils import timezone as django_timezone
from django.utils import six
from django.utils.encoding import python_2_unicode_compatible
from django.contrib.contenttypes import models as ct_models
from django.contrib.contenttypes import fields as ct_fields
from django_fsm import transition, FSMIntegerField
from jsonfield import JSONField

from nodeconductor.core import models as core_models
from nodeconductor.core import fields as core_fields
from nodeconductor.backup import managers, exceptions, utils
from nodeconductor.logging.loggers import LoggableMixin


logger = logging.getLogger(__name__)

class BackupSourceAbstractModel(models.Model):
    """
    Abstract model with generic key to backup source
    """
    # reference to the backed up object
    content_type = models.ForeignKey(ct_models.ContentType)
    object_id = models.PositiveIntegerField()
    backup_source = ct_fields.GenericForeignKey('content_type', 'object_id')

    class Meta(object):
        abstract = True


@python_2_unicode_compatible
class BackupSchedule(core_models.UuidMixin,
                     core_models.DescribableMixin,
                     LoggableMixin,
                     BackupSourceAbstractModel):
    """
    Model representing a backup schedule for a generic object.
    """
    # backup specific settings
    retention_time = models.PositiveIntegerField(
        help_text='Retention time in days')  # if 0 - backup will be kept forever
    maximal_number_of_backups = models.PositiveSmallIntegerField()
    schedule = core_fields.CronScheduleField(max_length=15)
    next_trigger_at = models.DateTimeField(null=True)
    is_active = models.BooleanField(default=False)
    timezone = models.CharField(max_length=50, default=django_timezone.get_current_timezone_name)

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
        base_time = django_timezone.now().replace(tzinfo=pytz.timezone(self.timezone))
        self.next_trigger_at = croniter(self.schedule, base_time).get_next(datetime)

    def _check_backup_source_state(self):
        """
        Backup source should be stable state.
        """
        state = self.backup_source.state
        if state not in self.backup_source.States.STABLE_STATES:
            logger.warning('Cannot execute backup schedule for %s in state %s.' % (self.backup_source, state))
            return False

        return True

    def _create_backup(self):
        """
        Creates new backup based on schedule and starts backup process
        """
        if not self._check_backup_source_state():
            return

        kept_until = django_timezone.now() + timedelta(days=self.retention_time) if self.retention_time else None
        backup = Backup.objects.create(
            backup_schedule=self,
            backup_source=self.backup_source,
            kept_until=kept_until,
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

        if prev_instance is None or (not prev_instance.is_active and self.is_active or
                                     self.schedule != prev_instance.schedule):
            self._update_next_trigger_at()

        super(BackupSchedule, self).save(*args, **kwargs)

    def get_log_fields(self):
        return ('uuid', 'name', 'backup_source')


@python_2_unicode_compatible
class Backup(core_models.UuidMixin,
             core_models.DescribableMixin,
             LoggableMixin,
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
        READY = 1
        BACKING_UP = 2
        RESTORING = 3
        DELETING = 4
        ERRED = 5
        DELETED = 6

    STATE_CHOICES = (
        (States.READY, 'Ready'),
        (States.BACKING_UP, 'Backing up'),
        (States.RESTORING, 'Restoring'),
        (States.DELETING, 'Deleting'),
        (States.ERRED, 'Erred'),
        (States.DELETED, 'Deleted'),
    )

    state = FSMIntegerField(default=States.READY, choices=STATE_CHOICES)
    metadata = JSONField(
        blank=True,
        help_text='Additional information about backup, can be used for backup restoration or deletion',
    )

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
        self.__save()
        tasks.process_backup_task.delay(self.uuid.hex)

    def start_restoration(self, instance_uuid, user_input, snapshot_ids):
        """
        Starts backup restoration task.
        """
        from nodeconductor.backup import tasks

        self._starting_restoration()
        self.__save()
        # all user input is supposed to be strings/numbers
        tasks.restoration_task.delay(self.uuid.hex, instance_uuid.hex, user_input, snapshot_ids)

    def start_deletion(self):
        """
        Starts backup deletion task
        """
        from nodeconductor.backup import tasks

        self._starting_deletion()
        self.__save()
        tasks.deletion_task.delay(self.uuid.hex)

    def set_metadata(self, metadata):
        self.metadata = metadata
        self.__save()

    def confirm_backup(self):
        self._confirm_backup()
        self.__save()

    def confirm_restoration(self):
        self._confirm_restoration()
        self.__save()

    def confirm_deletion(self):
        self._confirm_deletion()
        self.__save()

    def erred(self):
        self._erred()
        self.__save()

    def get_strategy(self):
        try:
            return utils.get_object_backup_strategy(self.backup_source)
        except KeyError:
            six.reraise(exceptions.BackupStrategyNotFoundError, exceptions.BackupStrategyNotFoundError())

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

    def get_log_fields(self):
        return ('uuid', 'name', 'backup_source')


class BackupStrategy(object):
    """
    A parent class for the model-specific backup strategies.
    """
    @classmethod
    def get_model(cls):
        raise NotImplementedError(
            'Implement get_model() that would return model.')

    @classmethod
    def backup(cls, backup_source):
        raise NotImplementedError(
            'Implement backup() that would perform backup of a model.')

    @classmethod
    def restore(cls, backup_source, metadata, user_input):
        raise NotImplementedError(
            'Implement restore() that would perform backup of a model.')

    @classmethod
    def get_restoration_serializer(cls, backup_source, metadata, user_input):
        raise NotImplementedError(
            'Implement get_restoration_serializer() that would perform backup of a model.')

    @classmethod
    def delete(cls, backup_source, metadata):
        raise NotImplementedError(
            'Implement delete() that would perform backup of a model.')
