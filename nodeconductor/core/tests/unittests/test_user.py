from __future__ import unicode_literals

import unittest

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone


class TestUser(unittest.TestCase):

    @override_settings(NODECONDUCTOR={'TOKEN_LIFETIME': timezone.timedelta(days=1)})
    def test_token_lifetime_is_read_from_settings_as_default_value_when_user_is_created(self):
        token_lifetime = settings.NODECONDUCTOR['TOKEN_LIFETIME']
        expected_lifetime = int(token_lifetime.total_seconds())
        user = get_user_model().objects.create(username='test1')
        self.assertEqual(user.token_lifetime, expected_lifetime)

    @override_settings(NODECONDUCTOR={'TOKEN_LIFETIME': None})
    def test_token_lifetime_is_null_if_settings_are_empty(self):
        user = get_user_model().objects.create(username='test2')
        self.assertEqual(user.token_lifetime, None)
