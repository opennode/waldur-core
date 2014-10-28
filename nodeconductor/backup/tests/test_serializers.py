from django.core.exceptions import ValidationError
from django.test import TestCase
from django.core.urlresolvers import reverse, resolve
from django.test.client import RequestFactory

from nodeconductor.backup.tests import factories
from nodeconductor.backup import serializers, models, backup_registry


class RelatedBackupFieldTest(TestCase):

    def setUp(self):
        self.field = serializers.RelatedBackupField()

    def test_get_url(self):
        backup = factories.BackupFactory()
        self.assertEqual(self.field._get_url(backup), 'backup-detail')

    def test_to_native(self):
        backup = factories.BackupFactory()
        expected_url = 'http://testserver' + reverse('backup-detail', args=(backup.uuid, ))
        mocked_request = RequestFactory().get(reverse('backup-detail', args=(backup.uuid, )))
        self.field.context = {'request': mocked_request}
        self.assertEqual(self.field.to_native(backup), expected_url)

    def test_format_url(self):
        url = 'http://127.0.0.1:8000/backup/uuid/'
        self.assertEqual(self.field._format_url(url), '/backup/uuid/')

    def test_get_model_from_resolve_match(self):
        backup = factories.BackupFactory()
        backup_url = reverse('backup-detail', args=(backup.uuid, ))
        match = resolve(backup_url)
        self.assertEqual(self.field._get_model_from_resolve_match(match), models.Backup)

    def test_from_native(self):
        # url is ok
        backup = factories.BackupFactory()
        backup_url = 'http://testserver' + reverse('backup-detail', args=(backup.uuid, ))
        self.assertEqual(self.field.from_native(backup_url), backup)
        # url is wrong
        url = 'http://testserver/abrakadabra/'
        self.assertRaises(ValidationError, lambda: self.field.from_native(url))


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
        # backup_source is backupable
        backup_registry.BACKUP_REGISTRY = {'Test': 'backup_backup'}
        serializer = serializers.BackupScheduleSerializer(data=backup_schedule_data)
        self.assertTrue(serializer.is_valid())
