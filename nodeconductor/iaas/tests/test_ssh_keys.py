from rest_framework import test, status

from nodeconductor.core import models as core_models
from nodeconductor.iaas.tests import factories
from nodeconductor.structure.tests import factories as structure_factories


class SshKeyRetreiveListTest(test.APITransactionTestCase):

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
