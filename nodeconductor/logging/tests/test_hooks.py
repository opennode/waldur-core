from django.core.urlresolvers import reverse
from rest_framework import status, test

from nodeconductor.logging import loggers
from nodeconductor.logging.tests.factories import WebHookFactory, PushHookFactory
from nodeconductor.structure.tests import factories as structure_factories


class BaseHookApiTest(test.APITransactionTestCase):
    def setUp(self):
        self.staff = structure_factories.UserFactory(is_staff=True)
        self.author = structure_factories.UserFactory()
        self.other_user = structure_factories.UserFactory()

        self.valid_event_types = loggers.get_valid_events()[:3]
        self.valid_event_groups = loggers.get_event_groups_keys()


class HookCreationViewTest(BaseHookApiTest):

    def test_user_can_create_webhook(self):
        self.client.force_authenticate(user=self.author)
        response = self.client.post(WebHookFactory.get_list_url(), data={
            'event_types': self.valid_event_types,
            'destination_url': 'http://example.com/'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

    def test_user_can_create_email_hook(self):
        self.client.force_authenticate(user=self.author)
        response = self.client.post(reverse('emailhook-list'), data={
            'event_types': self.valid_event_types,
            'email': 'test@example.com'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

    def test_user_can_create_push_hook(self):
        self.client.force_authenticate(user=self.author)
        response = self.client.post(PushHookFactory.get_list_url(), data={
            'event_types': self.valid_event_types,
            'token': 'VALID_TOKEN',
            'type': 'Android'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

    def test_user_can_subscribe_to_event_groups(self):
        event_groups = self.valid_event_groups
        event_types = loggers.expand_event_groups(event_groups)

        self.client.force_authenticate(user=self.author)
        response = self.client.post(WebHookFactory.get_list_url(), data={
            'event_groups': event_groups,
            'destination_url': 'http://example.com/'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['event_groups'], set(event_groups))
        self.assertEqual(response.data['event_types'], set(event_types))


class BaseHookUpdateTest(BaseHookApiTest):
    def update_hook(self, data):
        self.client.force_authenticate(user=self.author)
        response = self.client.patch(self.url, data=data)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        return response


class WebHookUpdateTest(BaseHookUpdateTest):

    def setUp(self):
        super(WebHookUpdateTest, self).setUp()
        self.webhook = WebHookFactory(user=self.author)
        self.url = WebHookFactory.get_url(self.webhook)

    def test_author_can_update_webhook_destination_url(self):
        data = {
            'destination_url': 'http://another-host.com'
        }
        response = self.update_hook(data)
        self.assertEqual(data['destination_url'], response.data['destination_url'])

    def test_author_can_update_webhook_event_types(self):
        data = {
            'event_types': set(self.valid_event_types[:1]),
        }
        response = self.update_hook(data)
        self.assertEqual(data['event_types'], response.data['event_types'])

    def test_author_can_update_event_groups(self):
        event_groups = self.valid_event_groups
        event_types = loggers.expand_event_groups(event_groups)

        self.client.force_authenticate(user=self.author)
        response = self.update_hook({
            'event_groups': event_groups
        })
        self.assertEqual(response.data['event_groups'], set(event_groups))
        self.assertEqual(response.data['event_types'], set(event_types))

    def test_author_can_disable_webhook(self):
        response = self.update_hook({'is_active': False})
        self.assertFalse(response.data['is_active'])


class PushHookUpdateTest(BaseHookUpdateTest):

    def setUp(self):
        super(PushHookUpdateTest, self).setUp()
        self.hook = PushHookFactory(user=self.author)
        self.url = PushHookFactory.get_url(self.hook)

    def test_author_can_update_push_hook_token(self):
        data = {
            'token': 'NEW_VALID_TOKEN'
        }
        response = self.update_hook(data)
        self.assertEqual(data['token'], response.data['token'])

    def test_author_can_update_push_hook_event_types(self):
        new_events = set(self.valid_event_types[:1])
        data = {
            'event_types': new_events,
        }
        response = self.update_hook(data)
        self.assertEqual(data['event_types'], response.data['event_types'])

    def test_author_can_disable_push_hook(self):
        response = self.update_hook({'is_active': False})
        self.assertFalse(response.data['is_active'])


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
