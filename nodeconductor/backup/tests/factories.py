import factory

from nodeconductor.backup import models
from nodeconductor.cloud.tests.factories import FlavorFactory


class BackupScheduleFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.BackupSchedule

    backup_source = factory.SubFactory(FlavorFactory)
    retention_time = 10
    is_active = True
    maximal_number_of_backups = 3
    schedule = '*/5 * * * *'


class BackupFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.Backup

    backup_schedule = factory.SubFactory(BackupScheduleFactory)
    backup_source = factory.LazyAttribute(lambda b: b.backup_schedule.backup_source)
