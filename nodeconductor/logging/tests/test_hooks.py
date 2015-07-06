import unittest

from django.core.urlresolvers import reverse
from rest_framework import status, test, settings

from nodeconductor.logging import models, log, serializers
from nodeconductor.structure.tests import factories as structure_factories


class HookSerializerTest(unittest.TestCase):
    def setUp(self):
        self.events = serializers.get_valid_events()[:3]

    def test_valid_web_settings(self):
        serializer = serializers.HookSerializer(data={
            'events': self.events,
            'name': 'web',
            'settings': {
                'url': 'http://example.com/'
            }
        })
        self.assertTrue(serializer.is_valid())

    def test_valid_email_settings(self):
        serializer = serializers.HookSerializer(data={
            'events': self.events,
            'name': 'email',
            'settings': {
                'email': 'test@example.com'
            }
        })
        self.assertTrue(serializer.is_valid())

    def test_invalid_web_settings(self):
        serializer = serializers.HookSerializer(data={
            'events': self.events,
            'name': 'web',
            'settings': {
                'url': 'INVALID_URL'
            }
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('url', serializer.errors['settings'])

    def test_invalid_events(self):
        serializer = serializers.HookSerializer(data={
            'events': ['INVALID_EVENT'],
            'name': 'web',
            'settings': {
                'url': 'http://example.com/'
            }
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('events', serializer.errors)


class HookViewTest(test.APITransactionTestCase):
    def setUp(self):
        self.url = reverse('hook-list')
        self.staff = structure_factories.UserFactory(is_staff=True)
        self.author = structure_factories.UserFactory()
        self.other_user = structure_factories.UserFactory()
        self.data = {
            'events': serializers.get_valid_events()[:3],
            'name': 'web',
            'settings': {
                'url': 'http://example.com/'
            }
        }

        self.client.force_authenticate(user=self.author)
        response = self.client.post(self.url, data=self.data)
        self.url = response.data['url']

    def test_hook_visible_to_author(self):
        self.client.force_authenticate(user=self.author)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(self.author.uuid, response.data['author_uuid'])

    def test_hook_visible_to_staff(self):
        self.client.force_authenticate(user=self.staff)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

    def test_hook_not_visible_to_other_user(self):
        self.client.force_authenticate(user=self.other_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND, response.data)

    def test_author_can_update_hook(self):
        new_events = serializers.get_valid_events()[:2]
        self.client.force_authenticate(user=self.author)
        data = {
            'events': new_events,
            'name': 'email',
            'settings': {
                'email': 'test@example.com'
            }
        }
        response = self.client.put(self.url, data=data)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(data['events'], response.data['events'])
        self.assertEqual(data['settings'], response.data['settings'])
