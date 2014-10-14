from __future__ import unicode_literals

from django.test import TestCase

from rest_framework.exceptions import PermissionDenied

from nodeconductor.structure.tests import factories as structure_factories
from nodeconductor.structure import models as structure_models
from nodeconductor.cloud.tests import factories
from nodeconductor.cloud import views, models


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


class SecurityGroupsViewSetTest(TestCase):

    def setUp(self):
        self.view = views.SecurityGroupsViewSet()

    def test_list(self):
        response = self.view.list(None)
        self.assertSequenceEqual(response.data, models.SecurityGroups.groups)
