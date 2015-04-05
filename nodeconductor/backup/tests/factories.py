import factory

from django.core.urlresolvers import reverse

from nodeconductor.backup import models
from nodeconductor.iaas import models as iaas_models
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

    @factory.post_generation
    def metadata(self, create, extracted, **kwargs):
        if not create:
            return

        self.metadata = {}

        cloud = self.backup_source.cloud_project_membership.cloud
        template = self.backup_source.template

        # check if image connecting template and cloud already exists, otherwise link them
        if not iaas_models.Image.objects.filter(cloud=cloud, template=template).exists():
            iaas_factories.ImageFactory(
                cloud=cloud,
                template=template,
            )

        self.metadata.update(
            {
                'cloud_project_membership': self.backup_source.cloud_project_membership.pk,
                'name': 'original.vm.name',
                'template': template.pk,
                'system_snapshot_id': self.backup_source.system_volume_id,
                'system_snapshot_size': self.backup_source.system_volume_size,
                'data_snapshot_id': self.backup_source.data_volume_id,
                'data_snapshot_size': self.backup_source.data_volume_size,
                'key_name': self.backup_source.key_name,
                'key_fingerprint': self.backup_source.key_name,
                'agreed_sla': self.backup_source.agreed_sla,
            }
        )
        if extracted:
            self.metadata.update(extracted)

    @classmethod
    def get_url(self, backup):
        if backup is None:
            backup = BackupFactory()
        return 'http://testserver' + reverse('backup-detail', kwargs={'uuid': backup.uuid})

    @classmethod
    def get_list_url(self):
        return 'http://testserver' + reverse('backup-list')
