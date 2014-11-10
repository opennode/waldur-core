from django.test import TestCase
from django.utils import unittest
from keystoneclient.exceptions import ClientException
from mock import patch

from nodeconductor.cloud import models, tasks
from nodeconductor.cloud.tests import factories, helpers


@unittest.skip('Reconsider these tests')
class TestTasks(TestCase):

    def test_connect_project_to_cloud_success(self):
        membership = factories.CloudProjectMembershipFactory()
        with patch('nodeconductor.cloud.models.keystone_client.Client', return_value=helpers.KeystoneMockedClient):
            tasks.push_cloud_membership(membership.pk)
            self.assertEqual(
                models.CloudProjectMembership.objects.get(pk=membership.pk).state,
                models.CloudProjectMembership.States.READY)

    def test_connect_project_to_cloud_error(self):
        membership = factories.CloudProjectMembershipFactory()
        with patch('nodeconductor.cloud.models.keystone_client.Client', side_effect=ClientException()):
            tasks.push_cloud_membership(membership.pk)
            self.assertEqual(
                models.CloudProjectMembership.objects.get(pk=membership.pk).state,
                models.CloudProjectMembership.States.ERRED)
