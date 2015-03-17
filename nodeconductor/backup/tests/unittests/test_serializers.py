from django.test import TestCase
from django.core.urlresolvers import reverse

from nodeconductor.backup.tests import factories
from nodeconductor.backup import serializers
from nodeconductor.iaas.tests import factories as iaas_factories


class BackupScheduleSerializerTest(TestCase):

    def test_validate_backup_source(self):
        # backup_source is unbackupable
        backup = factories.BackupFactory()
        backup_url = 'http://testserver' + reverse('backup-detail', args=(backup.uuid, ))
        backup_schedule_data = {
            'retention_time': 3,
            'backup_source': backup_url,
            'schedule': '*/5 * * * *',
            'maximal_number_of_backups': 3,
        }
        serializer = serializers.BackupScheduleSerializer(data=backup_schedule_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('backup_source', serializer.errors)
        # instance is backupable
        backup_schedule_data['backup_source'] = iaas_factories.InstanceFactory.get_url()
        serializer = serializers.BackupScheduleSerializer(data=backup_schedule_data)
        self.assertTrue(serializer.is_valid())
