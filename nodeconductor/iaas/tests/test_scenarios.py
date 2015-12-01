from __future__ import unicode_literals

from django.core.urlresolvers import reverse
from mock import patch
from rest_framework import status
from rest_framework import test

from nodeconductor.iaas import serializers
from nodeconductor.iaas.tests import factories
from nodeconductor.structure import models as structure_models
from nodeconductor.structure.tests import factories as structure_factories


def _cloud_url(cloud, action=None):
    url = 'http://testserver' + reverse('cloud-detail', args=(str(cloud.uuid), ))
    return url if action is None else url + action + '/'


def _security_group_list_url():
    return 'http://testserver' + reverse('security_group-list')


def _security_group_detail_url(security_group):
    return 'http://testserver' + reverse('security_group-detail', args=(str(security_group.uuid), ))


class CloudTest(test.APISimpleTestCase):

    def setUp(self):
        self.customer = structure_factories.CustomerFactory()
        self.owner = structure_factories.UserFactory()
        self.customer.add_user(self.owner, structure_models.CustomerRole.OWNER)

        self.admin = structure_factories.UserFactory()
        self.manager = structure_factories.UserFactory()
        self.group_manager = structure_factories.UserFactory()
        self.project = structure_factories.ProjectFactory(customer=self.customer)
        self.project.add_user(self.admin, structure_models.ProjectRole.ADMINISTRATOR)
        self.project.add_user(self.manager, structure_models.ProjectRole.MANAGER)
        project_group = structure_factories.ProjectGroupFactory(customer=self.customer)
        project_group.projects.add(self.project)
        project_group.add_user(self.group_manager, structure_models.ProjectGroupRole.MANAGER)
        self.cloud = factories.CloudFactory(customer=self.customer)
        factories.CloudProjectMembershipFactory(cloud=self.cloud, project=self.project)

        self.expected_public_fields = (
            'auth_url', 'uuid', 'url', 'name',
            'customer', 'customer_name', 'customer_native_name',
            'flavors', 'projects', 'resources_count', 'service_type'
        )

    def test_admin_can_view_only_cloud_public_fields(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(_cloud_url(self.cloud))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertItemsEqual(response.data.keys(), self.expected_public_fields)

    def test_manager_can_view_only_cloud_public_fields(self):
        self.client.force_authenticate(user=self.manager)
        response = self.client.get(_cloud_url(self.cloud))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertItemsEqual(response.data.keys(), self.expected_public_fields)

    def test_group_manager_can_view_only_cloud_public_fields(self):
        self.client.force_authenticate(user=self.group_manager)
        response = self.client.get(_cloud_url(self.cloud))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertItemsEqual(response.data.keys(), self.expected_public_fields)

    def test_custmer_owner_can_view_all_cloud_fields(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(_cloud_url(self.cloud))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertItemsEqual(response.data.keys(), serializers.CloudSerializer.Meta.fields)

    def test_manager_who_also_is_owner_can_view_all_cloud_fields(self):
        self.project.add_user(self.owner, structure_models.ProjectRole.MANAGER)
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(_cloud_url(self.cloud))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertItemsEqual(response.data.keys(), serializers.CloudSerializer.Meta.fields)
