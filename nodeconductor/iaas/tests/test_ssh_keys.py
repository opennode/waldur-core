from __future__ import unicode_literals

import unittest

from mock import patch
from rest_framework import test, status
from django.core.urlresolvers import reverse

from nodeconductor.core import models as core_models
from nodeconductor.iaas import serializers
from nodeconductor.iaas import views
from nodeconductor.iaas.tests import factories
from nodeconductor.structure.tests import factories as structure_factories
from nodeconductor.structure.models import CustomerRole, ProjectRole


class SshKeyViewSetTest(unittest.TestCase):
    def setUp(self):
        self.view_set = views.SshKeyViewSet()

    def test_cannot_modify_public_key_in_place(self):
        self.assertNotIn('PUT', self.view_set.allowed_methods)
        self.assertNotIn('PATCH', self.view_set.allowed_methods)

    def test_ssh_key_serializer_serializer_is_used(self):
        self.assertIs(
            serializers.SshKeySerializer,
            self.view_set.get_serializer_class(),
        )


class SshKeyRetrieveListTest(test.APITransactionTestCase):

    def setUp(self):
        self.staff = structure_factories.UserFactory(is_staff=True)
        self.user = structure_factories.UserFactory()
        self.user_key = factories.SshPublicKeyFactory(user=self.user)

    #  TODO: move this test to permissions test
    def test_admin_can_access_any_key(self):
        self.client.force_authenticate(self.staff)
        url = factories.SshPublicKeyFactory.get_url(self.user_key)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class SshKeyCreateDeleteTest(test.APITransactionTestCase):

    def setUp(self):
        self.staff = structure_factories.UserFactory(is_staff=True)
        self.user = structure_factories.UserFactory()
        self.user_key = factories.SshPublicKeyFactory(user=self.user)

    def test_key_user_and_name_uniqueness(self):
        self.client.force_authenticate(self.user)
        data = {
            'name': self.user_key.name,
            'public_key': self.user_key.public_key,
        }

        response = self.client.post(factories.SshPublicKeyFactory.get_list_url(), data=data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertDictContainsSubset(
            {'name': ['This field must be unique.']}, response.data)

    def test_valid_key_creation(self):
        self.client.force_authenticate(self.user)
        data = {
            'name': 'key#2',
            'public_key': self.user_key.public_key,
        }
        response = self.client.post(factories.SshPublicKeyFactory.get_list_url(), data=data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.assertTrue(core_models.SshPublicKey.objects.filter(name=data['name']).exists(),
                        'New key should have been created in the database')

    def test_staff_user_can_delete_any_key(self):
        self.client.force_authenticate(self.staff)
        response = self.client.delete(factories.SshPublicKeyFactory.get_url(self.user_key))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_user_can_delete_his_key(self):
        self.client.force_authenticate(self.user)
        response = self.client.delete(factories.SshPublicKeyFactory.get_url(self.user_key))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_user_cannot_delete_other_users_key(self):
        other_key = factories.SshPublicKeyFactory()
        self.client.force_authenticate(self.user)
        response = self.client.delete(factories.SshPublicKeyFactory.get_url(other_key))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class SshKeyPropagationTest(test.APITransactionTestCase):

    def setUp(self):
        self.owner = structure_factories.UserFactory(is_staff=True, is_superuser=True)
        # self.user = structure_factories.UserFactory()
        # self.user_key = factories.SshPublicKeyFactory(user=self.user)

    def _get_project_url(self, project):
        return 'http://testserver' + reverse('project-detail', kwargs={'uuid': project.uuid})

    def _get_cloud_url(self, cloud):
        return 'http://testserver' + reverse('cloud-detail', kwargs={'uuid': cloud.uuid})

    def _get_ssh_key_url(self, ssh_key):
        return 'http://testserver' + reverse('sshpublickey-detail', kwargs={'uuid': ssh_key.uuid})

    def test_user_key_synced_on_creation_and_deletion(self):
        customer = structure_factories.CustomerFactory()
        customer.add_user(self.owner, CustomerRole.OWNER)

        project = structure_factories.ProjectFactory(customer=customer)
        cloud = factories.CloudFactory(auth_url='http://example.com:5000/v2', customer=customer)

        self.client.force_authenticate(self.owner)

        membership = factories.CloudProjectMembershipFactory(cloud=cloud, project=project)

        # Test user add/remove key
        with patch('nodeconductor.iaas.tasks.iaas.push_ssh_public_keys.delay') as mocked_task:
            ssh_key = factories.SshPublicKeyFactory(user=self.owner)
            mocked_task.assert_called_with([ssh_key.uuid.hex], [membership.pk])

            with patch('nodeconductor.iaas.tasks.iaas.remove_ssh_public_keys.delay') as mocked_task:
                self.client.delete(self._get_ssh_key_url(ssh_key))
                mocked_task.assert_called_with([ssh_key.uuid.hex], [membership.pk])

        user = structure_factories.UserFactory()
        user_key = factories.SshPublicKeyFactory(user=user)

        # Test user add/remove from project
        with patch('nodeconductor.iaas.tasks.iaas.push_ssh_public_keys.delay') as mocked_task:
            project.add_user(user, ProjectRole.ADMINISTRATOR)
            mocked_task.assert_called_with([user_key.uuid.hex], [membership.pk])

            with patch('nodeconductor.iaas.tasks.iaas.remove_ssh_public_keys.delay') as mocked_task:
                project.remove_user(user)
                mocked_task.assert_called_with([user_key.uuid.hex], [membership.pk])
