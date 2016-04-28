from django.contrib.auth import get_user_model
from django.core.urlresolvers import reverse
from django.utils import timezone

from mock import patch

from rest_framework import test, status
from rest_framework.authtoken.models import Token


class TokenAuthenticationTest(test.APITransactionTestCase):
    def setUp(self):
        self.username = 'test'
        self.password = 'secret'
        self.auth_url = 'http://testserver' + reverse('auth-password')
        self.test_url = 'http://testserver/api/'
        get_user_model().objects.create_user(self.username, 'admin@example.com', self.password)

    def test_user_can_authenticate_with_token(self):
        response = self.client.post(self.auth_url, data={'username': self.username, 'password': self.password})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        token = response.data['token']
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + token)
        response = self.client.get(self.test_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_cannot_use_expired_token(self):
        response = self.client.post(self.auth_url, data={'username': self.username, 'password': self.password})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        token = response.data['token']
        mocked_now = timezone.now() + timezone.timedelta(hours=1)
        with patch('django.utils.timezone.now', lambda: mocked_now):
            self.client.credentials(HTTP_AUTHORIZATION='Token ' + token)
            response = self.client.get(self.test_url)
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
            self.assertEqual(response.data['detail'], 'Token has expired.')

    def test_token_creation_time_is_updated_on_every_request(self):
        response = self.client.post(self.auth_url, data={'username': self.username, 'password': self.password})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        token = response.data['token']
        created1 = Token.objects.values_list('created', flat=True).get(key=token)

        self.client.credentials(HTTP_AUTHORIZATION='Token ' + token)
        self.client.get(self.test_url)
        created2 = Token.objects.values_list('created', flat=True).get(key=token)
        self.assertTrue(created1 < created2)

    def test_token_is_recreated_on_successful_authentication(self):
        response = self.client.post(self.auth_url, data={'username': self.username, 'password': self.password})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        token1 = response.data['token']

        response = self.client.post(self.auth_url, data={'username': self.username, 'password': self.password})
        token2 = response.data['token']
        self.assertNotEqual(token1, token2)
