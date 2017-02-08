from __future__ import unicode_literals

import unittest

from django.conf import settings
from django.contrib.auth import get_user_model


class TestUser(unittest.TestCase):

    def test_token_lifetime_is_read_from_settings_as_default_value_when_user_is_created(self):
        expected_lifetime = getattr(settings.NODECONDUCTOR['TOKEN_LIFETIME'], 'seconds', None)
        user = get_user_model().objects.create()
        self.assertEqual(user.token_lifetime, expected_lifetime)
