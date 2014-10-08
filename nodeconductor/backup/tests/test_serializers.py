from django.core.exceptions import ObjectDoesNotExist
from django.test import TestCase
from django.core.urlresolvers import reverse, resolve

from nodeconductor.backup.tests import factories
from nodeconductor.backup import serializers, models


class RelatedBackupFieldTest(TestCase):

    def setUp(self):
        self.field = serializers.RelatedBackupField()

    def test_get_url(self):
        backup = factories.BackupFactory()
        self.assertEqual(self.field._get_url(backup), 'backup-detail')

    def test_to_native(self):
        backup = factories.BackupFactory()
        expected_url = reverse('backup-detail', args=(backup.uuid, ))
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
        self.assertRaises(ObjectDoesNotExist, lambda: self.field.from_native(url))
