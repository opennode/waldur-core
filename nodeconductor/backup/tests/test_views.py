from __future__ import unicode_literals

from django.test import TestCase

from nodeconductor.backup import views, models, backup_registry
from nodeconductor.backup.tests import factories
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
        # only for test lets make backupschedule backupable
        backup_registry.BACKUP_REGISTRY = {'Schedule': 'backup_backupschedule'}
        backupable = factories.BackupScheduleFactory()
        factories.BackupFactory(backup_source=backupable)
        mocked_request = type(str('MockedRequest'), (object,), {'user': self.user})()
        # user can view backupable:
        self.filter._get_user_visible_model_instances_ids = lambda u, m: [backupable.id]
        filtered = self.filter.filter_queryset(mocked_request, models.Backup.objects.all(), None)
        self.assertEqual(len(models.Backup.objects.all()), len(filtered.values()))
        # user can`t view backupable:
        self.filter._get_user_visible_model_instances_ids = lambda u, m: []
        filtered = self.filter.filter_queryset(mocked_request, models.Backup.objects.all(), None)
        self.assertFalse(filtered)


class BackupViewSetTest(TestCase):

    def setUp(self):
        self.view = views.BackupViewSet()
        self.user = structure_factories.UserFactory.create(is_staff=True, is_superuser=True)

    def test_restore(self):
        backup = factories.BackupFactory(state=models.Backup.States.READY)
        request = type(str('MockedRequest'), (object, ), {'DATA': {'replace_original': True}, 'user': self.user})
        response = self.view.restore(request, backup.uuid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(models.Backup.objects.get(pk=backup.pk).state, models.Backup.States.RESTORING)

    def test_delete(self):
        request = type(str('MockedRequest'), (object, ), {'user': self.user})
        backup = factories.BackupFactory(state=models.Backup.States.READY)
        response = self.view.delete(request, backup.uuid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(models.Backup.objects.get(pk=backup.pk).state, models.Backup.States.DELETING)
