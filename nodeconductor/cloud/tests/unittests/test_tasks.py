from django.test import TestCase
from mock import patch

from nodeconductor.cloud import models, tasks
from nodeconductor.cloud.tests import factories, helpers


class TestTasks(TestCase):

    def test_connect_project_to_cloud_success(self):
        membership = factories.CloudProjectMembershipFactory()
        with patch('nodeconductor.cloud.models.client.Client', return_value=helpers.KeystoneMockedClient):
            tasks.create_backend_membership(membership)
            self.assertEqual(
                models.CloudProjectMembership.objects.get(pk=membership.pk).state,
                models.CloudProjectMembership.States.READY)

    def test_connect_project_to_cloud_error(self):
        membership = factories.CloudProjectMembershipFactory()
        with patch('nodeconductor.cloud.models.client.Client', side_effect=Exception()):
            tasks.create_backend_membership(membership)
            self.assertEqual(
                models.CloudProjectMembership.objects.get(pk=membership.pk).state,
                models.CloudProjectMembership.States.ERRED)
