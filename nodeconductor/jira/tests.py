from __future__ import unicode_literals

from rest_framework import status, test, settings

from django.core.urlresolvers import reverse
from django.test.utils import override_settings

from nodeconductor.structure.tests import factories as structure_factories


class JiraTest(test.APITransactionTestCase):

    def setUp(self):
        self.user = structure_factories.UserFactory()

    def get_issues_url(cls):
        return 'http://testserver' + reverse('issue-list')

    def get_comments_url(cls, key):
        return 'http://testserver' + reverse('issue-comments-list', kwargs={'pk': key})

    @override_settings(NODECONDUCTOR={'JIRA_DUMMY': True})
    def test_list_issues(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.get_issues_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertItemsEqual(['TST-1', 'TST-2', 'TST-3'], [issue.get('key') for issue in response.data])

    @override_settings(NODECONDUCTOR={'JIRA_DUMMY': True})
    def test_search_issues(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.get_issues_url(), data={settings.api_settings.SEARCH_PARAM: '^_^'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual('TST-3', response.data[0]['key'])

    @override_settings(NODECONDUCTOR={'JIRA_DUMMY': True})
    def test_create_issues(self):
        self.client.force_authenticate(user=self.user)
        data = {
            'summary': 'Just a test',
            'description': 'nothing more',
        }

        response = self.client.post(self.get_issues_url(), data=data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual('TST-4', response.data['key'])

    @override_settings(NODECONDUCTOR={'JIRA_DUMMY': True})
    def test_list_comments(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.get_comments_url('TST-3'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    @override_settings(NODECONDUCTOR={'JIRA_DUMMY': True})
    def test_create_comments(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.get_comments_url('TST-1'), data={'body': 'hi there'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('Alice', response.data['author']['displayName'])
