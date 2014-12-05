import factory

from django.core.urlresolvers import reverse

from nodeconductor.backup import models
from nodeconductor.iaas.tests import factories as iaas_factories


class BackupScheduleFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.BackupSchedule

    backup_source = factory.SubFactory(iaas_factories.InstanceFactory)
    retention_time = 10
    is_active = True
    maximal_number_of_backups = 3
    schedule = '*/5 * * * *'


class BackupFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = models.Backup

    backup_schedule = factory.SubFactory(BackupScheduleFactory)
    backup_source = factory.LazyAttribute(lambda b: b.backup_schedule.backup_source)

    @classmethod
    def get_url(self, backup):
        if backup is None:
            backup = BackupFactory()
        return 'http://testserver' + reverse('backup-detail', kwargs={'uuid': backup.uuid})

    @classmethod
    def get_list_url(self):
        return 'http://testserver' + reverse('backup-list')
