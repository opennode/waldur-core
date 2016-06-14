from django.core.urlresolvers import reverse
from rest_framework import status, test

from nodeconductor.logging import loggers
from nodeconductor.logging.tests.factories import WebHookFactory
from nodeconductor.structure.tests import factories as structure_factories


class BaseHookApiTest(test.APITransactionTestCase):
    def setUp(self):
        self.staff = structure_factories.UserFactory(is_staff=True)
        self.author = structure_factories.UserFactory()
        self.other_user = structure_factories.UserFactory()


class HookCreationViewTest(BaseHookApiTest):

    def test_user_can_create_webhook(self):
        self.client.force_authenticate(user=self.author)
        response = self.client.post(WebHookFactory.get_list_url(), data={
            'event_types': loggers.get_valid_events()[:3],
            'destination_url': 'http://example.com/'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

    def test_user_can_create_email_hook(self):
        self.client.force_authenticate(user=self.author)
        response = self.client.post(reverse('emailhook-list'), data={
            'event_types': loggers.get_valid_events()[:3],
            'email': 'test@example.com'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

    def test_user_can_subscribe_to_event_groups(self):
        event_groups = loggers.get_event_groups_keys()[:3]
        event_types = loggers.expand_event_groups(event_groups)

        self.client.force_authenticate(user=self.author)
        response = self.client.post(WebHookFactory.get_list_url(), data={
            'event_groups': event_groups,
            'destination_url': 'http://example.com/'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['event_groups'], set(event_groups))
        self.assertEqual(response.data['event_types'], set(event_types))


class HookPermisssionsViewTest(BaseHookApiTest):

    def setUp(self):
        super(HookPermisssionsViewTest, self).setUp()
        self.url = WebHookFactory.get_url(WebHookFactory(user=self.author))

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
        new_events = set(loggers.get_valid_events()[:2])
        self.client.force_authenticate(user=self.author)
        data = {
            'event_types': new_events,
            'destination_url': 'http://another-host.com'
        }
        response = self.client.put(self.url, data=data)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(data['event_types'], response.data['event_types'])
        self.assertEqual(data['destination_url'], response.data['destination_url'])
