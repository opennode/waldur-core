import unittest

from mock import patch
from rest_framework import status
from rest_framework import test

from django.core.urlresolvers import reverse

from nodeconductor.structure import SupportedServices
from nodeconductor.structure.models import ServiceSettings, CustomerRole
from nodeconductor.structure.tests import factories


class ServiceSettingsTest(test.APITransactionTestCase):
    def setUp(self):
        self.users = {
            'staff': factories.UserFactory(is_staff=True),
            'owner': factories.UserFactory(),
            'not_owner': factories.UserFactory(),
        }

        self.customers = {
            'owned': factories.CustomerFactory(),
            'inaccessible': factories.CustomerFactory(),
        }

        self.customers['owned'].add_user(self.users['owner'], CustomerRole.OWNER)

        self.settings = {
            'shared': factories.ServiceSettingsFactory(shared=True),
            'inaccessible': factories.ServiceSettingsFactory(customer=self.customers['inaccessible']),
            'owned': factories.ServiceSettingsFactory(
                customer=self.customers['owned'], backend_url='bk.url', password='123', type=SupportedServices.Types.OpenStack),
        }

        # Token is excluded, because it is not available for OpenStack
        self.credentials = ('backend_url', 'username', 'password')

    def _get_settings_url(self, settings=None):
        if settings:
            return 'http://testserver' + reverse('servicesettings-detail', kwargs={'uuid': settings.uuid})
        else:
            return 'http://testserver' + reverse('servicesettings-list')

    def test_user_can_see_shared_settings(self):
        self.client.force_authenticate(user=self.users['not_owner'])

        response = self.client.get(self._get_settings_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(len(response.data), 1)
        self.assert_credentials_hidden(response.data[0])
        self.assertEqual(response.data[0]['uuid'], self.settings['shared'].uuid.hex, response.data)

    def test_user_can_see_shared_and_own_settings(self):
        self.client.force_authenticate(user=self.users['owner'])

        response = self.client.get(self._get_settings_url())
        uuids_recieved = [d['uuid'] for d in response.data]
        uuids_expected = [self.settings[s].uuid.hex for s in ('shared', 'owned')]
        self.assertItemsEqual(uuids_recieved, uuids_expected, response.data)

    def test_admin_can_see_all_settings(self):
        self.client.force_authenticate(user=self.users['staff'])

        response = self.client.get(self._get_settings_url())
        uuids_recieved = [d['uuid'] for d in response.data]
        uuids_expected = [s.uuid.hex for s in self.settings.values()]
        self.assertItemsEqual(uuids_recieved, uuids_expected, uuids_recieved)

    def test_user_can_see_credentials_of_own_settings(self):
        self.client.force_authenticate(user=self.users['owner'])

        response = self.client.get(self._get_settings_url(self.settings['owned']))
        self.assert_credentials_visible(response.data)

    def test_user_cant_see_others_settings(self):
        self.client.force_authenticate(user=self.users['not_owner'])

        response = self.client.get(self._get_settings_url(self.settings['owned']))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_admin_can_see_all_credentials(self):
        self.client.force_authenticate(user=self.users['staff'])

        response = self.client.get(self._get_settings_url(self.settings['owned']))
        self.assert_credentials_visible(response.data)

    def test_user_cant_see_shared_credentials(self):
        self.client.force_authenticate(user=self.users['owner'])

        response = self.client.get(self._get_settings_url(self.settings['shared']))
        self.assert_credentials_hidden(response.data)

    def assert_credentials_visible(self, data):
        for field in self.credentials:
            self.assertIn(field, data)

    def assert_credentials_hidden(self, data):
        for field in self.credentials:
            self.assertNotIn(field, data)

    def test_user_cant_change_settings_type(self):
        self.client.force_authenticate(user=self.users['owner'])

        payload = {
            "name": "Test backend",
            "type": 2,
        }
        response = self.client.patch(self._get_settings_url(self.settings['owned']), payload)
        settings = ServiceSettings.objects.get(uuid=self.settings['owned'].uuid)
        self.assertNotEqual(settings.type, payload['type'], response.data)

    def test_user_can_change_settings_password(self):
        self.client.force_authenticate(user=self.users['owner'])

        payload = {
            "password": "secret",
        }
        response = self.client.patch(self._get_settings_url(self.settings['owned']), payload)
        settings = ServiceSettings.objects.get(uuid=self.settings['owned'].uuid)
        self.assertEqual(settings.password, payload['password'], response.data)

    @unittest.skip('Creating settings via common endpoint is disabled for now')
    def test_user_can_create_settings(self):
        self.client.force_authenticate(user=self.users['owner'])

        payload = {
            "customer": factories.CustomerFactory.get_url(self.customers['owned']),
            "name": "Test",
            "backend_url": "http://example.com",
            "username": "user",
            "password": "secret",
            "type": SupportedServices.Types.OpenStack,
        }

        with patch('celery.app.base.Celery.send_task') as mocked_task:
            response = self.client.post(self._get_settings_url(), payload)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

            settings = ServiceSettings.objects.get(name=payload['name'])
            self.assertFalse(settings.shared)

            mocked_task.assert_called_with(
                'nodeconductor.structure.sync_service_settings',
                (settings.uuid.hex,), {'initial': True})
