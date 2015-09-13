from __future__ import unicode_literals

import unittest

from rest_framework import test, status

from nodeconductor.core import models as core_models
from nodeconductor.structure import serializers
from nodeconductor.structure import views
from nodeconductor.structure.tests import factories


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
        self.staff = factories.UserFactory(is_staff=True)
        self.user = factories.UserFactory()
        self.user_key = factories.SshPublicKeyFactory(user=self.user)

    def test_admin_can_access_any_key(self):
        self.client.force_authenticate(self.staff)
        url = factories.SshPublicKeyFactory.get_url(self.user_key)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class SshKeyCreateDeleteTest(test.APITransactionTestCase):

    def setUp(self):
        self.staff = factories.UserFactory(is_staff=True)
        self.user = factories.UserFactory()
        self.user_key = factories.SshPublicKeyFactory(user=self.user)

    def test_key_user_and_name_uniqueness(self):
        self.client.force_authenticate(self.user)
        key = factories.SshPublicKeyFactory.build()
        data = {
            'name': self.user_key.name,
            'public_key': key.public_key,
        }

        response = self.client.post(factories.SshPublicKeyFactory.get_list_url(), data=data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertDictContainsSubset(
            {'name': ['This field must be unique.']}, response.data)

    def test_valid_key_creation(self):
        self.client.force_authenticate(self.user)
        key = factories.SshPublicKeyFactory.build()
        data = {
            'name': key.name,
            'public_key': key.public_key,
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

    def test_user_cannot_add_ssh_key_with_duplicate_fingerprint(self):
        staff = factories.UserFactory(is_staff=True)
        key = factories.SshPublicKeyFactory()
        data = {
            'name': 'test',
            'public_key': key.public_key,
        }

        self.client.force_authenticate(staff)
        response = self.client.post(factories.SshPublicKeyFactory.get_list_url(), data=data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(core_models.SshPublicKey.objects.filter(**data).exists())
