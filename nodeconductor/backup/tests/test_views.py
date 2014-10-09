from django.test import TestCase

from nodeconductor.backup import views, models
from nodeconductor.backup.tests import factories


class BackupViewSetTest(TestCase):

    def setUp(self):
        self.view = views.BackupViewSet()

    def test_restore(self):
        backup = factories.BackupFactory(state=models.Backup.States.READY)
        request = type('MockedRequest', (object, ), {'POST': {'replace_original': True}})
        response = self.view.restore(request, backup.uuid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(models.Backup.objects.get(pk=backup.pk).state, models.Backup.States.RESTORING)

    def test_delete(self):
        request = type('MockedRequest', (object, ), {})
        backup = factories.BackupFactory(state=models.Backup.States.READY)
        response = self.view.delete(request, backup.uuid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(models.Backup.objects.get(pk=backup.pk).state, models.Backup.States.DELETING)
