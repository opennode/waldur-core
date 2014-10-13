from __future__ import unicode_literals

from mock import patch

from django.core.urlresolvers import reverse

from rest_framework import test

from nodeconductor.structure.tests import factories as structure_factories
from nodeconductor.structure import models as structure_models
from nodeconductor.cloud.tests import factories


def _cloud_url(cloud, action=None):
    url = 'http://testserver' + reverse('cloud-detail', args=(str(cloud.uuid), ))
    return url if action is None else url + action + '/'


class CloudTest(test.APISimpleTestCase):

    def setUp(self):
        self.customer = structure_factories.CustomerFactory()
        self.owner = structure_factories.UserFactory()
        self.customer.add_user(self.owner, structure_models.CustomerRole.OWNER)

    def test_cloud_sync(self):
        cloud = factories.CloudFactory(customer=self.customer)
        self.client.force_authenticate(user=self.owner)
        with patch('nodeconductor.cloud.models.Cloud.sync') as patched_method:
            response = self.client.post(_cloud_url(cloud, action='sync'))
            patched_method.assert_called_with()
            self.assertEqual(response.status_code, 200)

    # XXX This method have to moved to cloud permissions test
    def test_cloud_sync_permission(self):
        user = structure_factories.UserFactory()
        cloud = factories.CloudFactory()
        self.client.force_authenticate(user=user)
        response = self.client.post(_cloud_url(cloud, action='sync'))
        self.assertEqual(response.status_code, 403)
