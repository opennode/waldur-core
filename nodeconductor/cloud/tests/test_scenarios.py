from __future__ import unicode_literals

import json

from django.core.urlresolvers import reverse

from mock import patch
from rest_framework import test

from nodeconductor.structure.tests import factories as structure_factories
from nodeconductor.structure import models as structure_models
from nodeconductor.cloud.tests import factories
from nodeconductor.cloud import models, serializers


def _cloud_url(cloud, action=None):
    url = 'http://testserver' + reverse('cloud-detail', args=(str(cloud.uuid), ))
    return url if action is None else url + action + '/'


def _security_group_list_url():
    return 'http://testserver' + reverse('security_group-list')


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

    # XXX This method have to be moved to cloud permissions test
    def test_cloud_sync_permission(self):
        user = structure_factories.UserFactory()
        cloud = factories.CloudFactory()
        self.client.force_authenticate(user=user)
        response = self.client.post(_cloud_url(cloud, action='sync'))
        self.assertEqual(response.status_code, 403)

    def test_cloud_visible_fields(self):
        """
        Tests that customer owner is able to see all fields, project admin and manager - only url, uuid and name
        """
        admin = structure_factories.UserFactory()
        manager = structure_factories.UserFactory()
        project = structure_factories.ProjectFactory(customer=self.customer)
        project.add_user(admin, structure_models.ProjectRole.ADMINISTRATOR)
        project.add_user(manager, structure_models.ProjectRole.MANAGER)
        cloud = factories.CloudFactory(customer=self.customer)
        cloud.projects.add(project)

        # admin
        self.client.force_authenticate(user=admin)
        response = self.client.get(_cloud_url(cloud))
        self.assertEqual(response.status_code, 200)
        context = json.loads(response.content)
        self.assertEqual(len(context.keys()), len(serializers.CloudSerializer.public_fields))
        for key in context.keys():
            self.assertIn(key, serializers.CloudSerializer.public_fields)

        # manager
        self.client.force_authenticate(user=admin)
        response = self.client.get(_cloud_url(cloud))
        self.assertEqual(response.status_code, 200)
        context = json.loads(response.content)
        self.assertEqual(len(context.keys()), len(serializers.CloudSerializer.public_fields))
        for key in context.keys():
            self.assertIn(key, serializers.CloudSerializer.public_fields)

        # customer owner
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(_cloud_url(cloud))
        self.assertEqual(response.status_code, 200)
        context = json.loads(response.content)
        self.assertGreater(len(context.keys()), len(serializers.CloudSerializer.public_fields))

        # customer is manager too
        project.add_user(self.owner, structure_models.ProjectRole.MANAGER)
        response = self.client.get(_cloud_url(cloud))
        self.assertEqual(response.status_code, 200)
        context = json.loads(response.content)
        self.assertGreater(len(context.keys()), len(serializers.CloudSerializer.public_fields))


class SecurityGroupsTest(test.APISimpleTestCase):

    def setUp(self):
        self.user = structure_factories.UserFactory()

    def test_list_security_groups(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(_security_group_list_url())
        self.assertEqual(response.status_code, 200)
