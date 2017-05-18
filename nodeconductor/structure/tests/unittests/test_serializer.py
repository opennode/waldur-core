from urlparse import urlparse

from django.contrib.auth import get_user_model
# XXX: Django 1.10 deprecation, import from django.urls
from django.core.urlresolvers import resolve
from django.test import TestCase

from rest_framework.test import APIRequestFactory
from .. import factories as structure_factories
from ...serializers import BasicUserSerializer

User = get_user_model()


class UUIDSerializerTest(TestCase):
    def setUp(self):
        factory = APIRequestFactory()
        request = factory.get('/users/')
        context = {'request': request}
        user = structure_factories.UserFactory()
        serializer = BasicUserSerializer(instance=user, context=context)
        self.data = serializer.data

    def test_url_and_uuid_do_not_contain_hyphenation(self):
        path = urlparse(self.data['url']).path
        match = resolve(path)
        self.assertEqual(match.url_name, 'user-detail')

        value = match.kwargs.get('uuid')
        self.assertEqual(value, self.data['uuid'])
        self.assertTrue('-' not in value)
