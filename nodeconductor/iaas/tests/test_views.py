from django.test import TestCase

from nodeconductor.structure.tests import factories as structure_factories
from nodeconductor.iaas import views


class InstanceViewSetTest(TestCase):

    def setUp(self):
        self.view = views.InstanceViewSet()

    def test_get_serializer_context(self):
        user = structure_factories.UserFactory()
        mocked_request = type(str('MockedRequest'), (object,), {'user': user})
        self.view.request = mocked_request
        self.view.format_kwarg = None
        self.assertEqual(user, self.view.get_serializer_context()['user'])
