from __future__ import unicode_literals

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone


class TestModels(TestCase):

    def test_token_lifetime_is_read_from_settings_as_default_value_when_user_is_created(self):
        nodeconductor_settings = settings.NODECONDUCTOR.copy()
        nodeconductor_settings['TOKEN_LIFETIME'] = timezone.timedelta(days=1)

        with self.settings(NODECONDUCTOR=nodeconductor_settings):
            token_lifetime = settings.NODECONDUCTOR['TOKEN_LIFETIME']
            expected_lifetime = int(token_lifetime.total_seconds())
            user = get_user_model().objects.create(username='test1')
            self.assertEqual(user.token_lifetime, expected_lifetime)
