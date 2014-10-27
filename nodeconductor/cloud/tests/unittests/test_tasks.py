from django.test import TestCase
from mock import patch

from nodeconductor.cloud import models, tasks
from nodeconductor.cloud.tests import factories, helpers
from nodeconductor.structure.tests import factories as structure_factories


class TestTasks(TestCase):

    def test_connect_project_to_cloud(self):
        project = structure_factories.ProjectFactory()
        cloud = factories.CloudFactory()
        with patch('nodeconductor.cloud.tasks.client.Client', return_value=helpers.KeystoneMockedClient):
            tasks.connect_project_to_cloud(project=project, cloud=cloud)
            self.assertEqual(models.CloudProjectMembership.objects.filter(project=project, cloud=cloud).count(), 1)
