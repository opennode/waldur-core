from __future__ import unicode_literals

from mock import Mock

from django.test import TestCase

from nodeconductor.backup import views, models
from nodeconductor.backup.tests import factories
from nodeconductor.iaas.tests import factories as iaas_factories
from nodeconductor.structure.tests import factories as structure_factories


class BackupPermissionFilterTest(TestCase):

    def setUp(self):
        self.filter = views.BackupPermissionFilter()
        self.user = structure_factories.UserFactory.create(is_staff=True, is_superuser=True)

    def test_get_user_visible_model_instances_ids(self):
        backup_ids = [factories.BackupFactory().pk for i in range(5)]
        self.assertSequenceEqual(
            backup_ids, self.filter._get_user_visible_model_instances_ids(self.user, models.Backup))

    def test_filter_queryset(self):
        backupable = iaas_factories.InstanceFactory()
        factories.BackupFactory(backup_source=backupable)
        mocked_request = Mock()
        mocked_request.user = self.user
        # user can view backupable:
        self.filter._get_user_visible_model_instances_ids = lambda u, m: [backupable.id]
        filtered = self.filter.filter_queryset(mocked_request, models.Backup.objects.all(), None)
        self.assertEqual(len(models.Backup.objects.all()), len(filtered.values()))
        # user can`t view backupable:
        self.filter._get_user_visible_model_instances_ids = lambda u, m: []
        filtered = self.filter.filter_queryset(mocked_request, models.Backup.objects.all(), None)
        self.assertFalse(filtered)
