from __future__ import unicode_literals

import unittest

from rest_framework import test, status

from nodeconductor.core import models as core_models
from nodeconductor.iaas import serializers
from nodeconductor.iaas import views
from nodeconductor.iaas.tests import factories
from nodeconductor.structure.tests import factories as structure_factories


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

    # TODO: add tests for key deletion
