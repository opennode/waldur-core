import factory

from nodeconductor.backup import models
from nodeconductor.cloud.tests.factories import FlavorFactory


class BackupScheduleFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.BackupSchedule

    name = factory.Sequence(lambda n: 'BackupSchedule#%s' % n)
    backup_source = factory.SubFactory(FlavorFactory)
    retention_time = 10
    is_active = True
    maximal_number_of_backups = 3
    schedule = '*/5 * * * *'


class BackupFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.Backup

    schedule = factory.SubFactory(BackupScheduleFactory)
    backup_source = factory.LazyAttribute(lambda b: b.schedule.backup_source)
