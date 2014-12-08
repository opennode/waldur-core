from django.test import TestCase

from rest_framework.exceptions import PermissionDenied

from nodeconductor.iaas import views
from nodeconductor.iaas.tests import factories
from nodeconductor.structure import models as structure_models
from nodeconductor.structure.tests import factories as structure_factories


class InstanceViewSetTest(TestCase):

    def setUp(self):
        self.view = views.InstanceViewSet()

    def test_get_serializer_context(self):
        user = structure_factories.UserFactory()
        mocked_request = type(str('MockedRequest'), (object,), {'user': user})
        self.view.request = mocked_request
        self.view.format_kwarg = None
        self.assertEqual(user, self.view.get_serializer_context()['user'])


class CloudViewSetTest(TestCase):

    def setUp(self):
        self.view = views.CloudViewSet()

    def test_check_permission(self):
        cloud = factories.CloudFactory()
        user = structure_factories.UserFactory()
        mocked_request = type(str('MockedRequest'), (object,), {'user': user})
        self.view.request = mocked_request
        self.assertRaises(PermissionDenied, lambda: self.view._check_permission(cloud))

    def test_sync(self):
        customer = structure_factories.CustomerFactory()
        owner = structure_factories.UserFactory()
        customer.add_user(owner, structure_models.CustomerRole.OWNER)

        cloud = factories.CloudFactory(customer=customer)
        mocked_request = type(str('MockedRequest'), (object,), {'user': owner})
        self.view.request = mocked_request
        response = self.view.sync(request=mocked_request, uuid=cloud.uuid)
        self.assertEqual(response.status_code, 200)
