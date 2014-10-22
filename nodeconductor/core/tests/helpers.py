from __future__ import unicode_literals

import json

from rest_framework import test


class PermissionsTest(test.APISimpleTestCase):
    """
    Abstract class for permissions tests.

    Methods `get_urls_configs`, `get_users_with_permission`,
    `get_users_without_permissions` have to be overridden.

    Logical example:

    class ExamplePermissionsTest(PermissionsTest):

        def get_users_with_permission(self, url, method):
            if is_unreachable(url):
                # no one can has access to unreachable url
                return []
            return [user_with_permission]

        def get_users_without_permissions(self, url, method):
            if is_unreachable(url):
                # everybody does not have access to to unreachable url
                return [user_with_permission, user_without_permission]
            return [user_without_permission]

        def get_urls_configs(self):
            yield {'url': 'http://testserver/some/url, 'method': 'GET'}
            yield {'url': 'http://testserver/some/unreachable/url', 'method': 'POST'}
            ...
    """

    def get_urls_configs(self):
        """
        Return list or generator of url configs.

        Each url config is dictionary with such keys:
         - url: url itself
         - method: request method
         - data: data which will be send in request
        url config example:
        {
            'url': 'http://testserver/api/backup/',
            'method': 'POST',
            'data': {'backup_source': 'backup/source/url'}
        }
        """
        raise NotImplementedError()

    def get_users_with_permission(self, url, method):
        """
        Returns list of users which can access given url with given method
        """
        raise NotImplementedError()

    def get_users_without_permissions(self, url, method):
        """
        Returns list of users which can not access given url with given method
        """
        raise NotImplementedError()

    def test_permissions(self):
        """
        Goes through all url configs ands checks that user with permissions
        can request them and users without - can't
        """
        for conf in self.get_urls_configs():
            url, method = conf['url'], conf['method']
            data = conf['data'] if 'data' in conf else {}

            for user in self.get_users_with_permission(url, method):
                self.client.force_authenticate(user=user)
                response = getattr(self.client, method.lower())(url, data=data)
                self.assertFalse(
                    response.status_code == 404 or response.status_code == 403,
                    'Error. User %s can not reach url: %s (method:%s). (Response status code %s)'
                    % (user, url, method, response.status_code))

            for user in self.get_users_without_permissions(url, method):
                self.client.force_authenticate(user=user)
                response = getattr(self.client, method.lower())(url, data=data)
                self.assertTrue(
                    response.status_code == 404 or response.status_code == 403,
                    'Error. User %s can reach url: %s (method:%s). (Response status code %s)'
                    % (user, url, method, response.status_code))


class ListPermissionsTest(test.APISimpleTestCase):
    """
    Abstract class that tests what objects user receive in list.

    Method `get_users_and_expected_results` has to be overridden.
    Field `url` have to be defined as class attribute or property.
    """
    url = None

    def get_users_and_expected_results(self):
        """
        Return list or generator of dictionaries with such keys:
         - user - user which we want to test
         - expected_results - list of dictionaries with fields which user has
                              to receive as answer from server
        """
        pass

    def test_list_permissions(self):
        for user_and_expected_result in self.get_users_and_expected_results():
            user = user_and_expected_result['user']
            expected_results = user_and_expected_result['expected_results']

            self.client.force_authenticate(user=user)
            response = self.client.get(self.url)
            context = json.loads(response.content)
            self.assertEqual(
                len(expected_results), len(context),
                'User %s receive wrong number of objects. Expected: %s, received %s'
                % (user, len(expected_results), len(context)))
            for actual, expected in zip(context, expected_results):
                for key, value in expected.iteritems():
                    self.assertEqual(actual[key], value)
