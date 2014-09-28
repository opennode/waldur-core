from __future__ import unicode_literals

from itertools import chain

from django.core.urlresolvers import reverse
from rest_framework import status
from rest_framework import test
from nodeconductor.cloud.models import Cloud

from nodeconductor.structure.models import CustomerRole
from nodeconductor.structure.models import ProjectRole
from nodeconductor.structure.tests import factories as structure_factories
from nodeconductor.cloud.tests import factories


# noinspection PyMethodMayBeStatic
class UrlResolverMixin(object):
    def _get_customer_url(self, customer):
        return 'http://testserver' + reverse('customer-detail', kwargs={'uuid': customer.uuid})

    def _get_project_url(self, project):
        return 'http://testserver' + reverse('project-detail', kwargs={'uuid': project.uuid})

    def _get_cloud_url(self, project):
        return 'http://testserver' + reverse('cloud-detail', kwargs={'uuid': project.uuid})


    def _get_membership_url(self, membership):
        return 'http://testserver' + reverse('projectcloud_membership-detail', kwargs={'pk': membership.pk})


ProjectCloudMembership = Cloud.projects.through


class ProjectCloudApiPermissionTest(UrlResolverMixin, test.APITransactionTestCase):
    def setUp(self):
        self.users = {
            'owner': structure_factories.UserFactory(),
            'admin': structure_factories.UserFactory(),
            'manager': structure_factories.UserFactory(),
            'no_role': structure_factories.UserFactory(),
            'not_connected': structure_factories.UserFactory(),
        }

        # a single customer
        self.customer = structure_factories.CustomerFactory()
        self.customer.add_user(self.users['owner'], CustomerRole.OWNER)
        self.customer.save()

        # that has 2 users connected: admin and manager
        self.connected_project = structure_factories.ProjectFactory(customer=self.customer)
        self.connected_project.add_user(self.users['admin'], ProjectRole.ADMINISTRATOR)
        self.connected_project.add_user(self.users['manager'], ProjectRole.MANAGER)
        self.connected_project.save()

        # has defined a cloud and connected cloud to a project
        self.cloud = factories.CloudFactory(customer=self.customer)
        self.cloud.projects.add(self.connected_project)
        self.cloud.save()

        # the customer also has another project with users but without a permission link
        self.not_connected_project = structure_factories.ProjectFactory(customer=self.customer)
        self.not_connected_project.add_user(self.users['not_connected'], ProjectRole.ADMINISTRATOR)
        self.not_connected_project.save()

    # Creation tests
    def test_anonymous_user_cannot_grant_cloud_to_project(self):
        response = self.client.post(reverse('projectcloud_membership-list'), self._get_valid_payload())
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_can_connect_cloud_and_project_he_owns(self):
        user = self.users['owner']
        self.client.force_authenticate(user=user)

        cloud = factories.CloudFactory(customer=self.customer)
        project = structure_factories.ProjectFactory(customer=self.customer)

        payload = self._get_valid_payload(cloud, project)

        response = self.client.post(reverse('projectcloud_membership-list'), payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_user_cannot_connect_new_cloud_and_project_if_he_is_project_admin(self):
        user = self.users['admin']
        self.client.force_authenticate(user=user)

        cloud = factories.CloudFactory(customer=self.customer)
        project = self.connected_project
        payload = self._get_valid_payload(cloud, project)

        response = self.client.post(reverse('projectcloud_membership-list'), payload)
        # the new cloud should not be visible to the user
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_cannot_revoke_cloud_and_project_permission_if_he_is_project_admin(self):
        user = self.users['admin']
        self.client.force_authenticate(user=user)

        project = self.connected_project
        cloud = self.cloud
        membership = ProjectCloudMembership.objects.get(project=project, cloud=cloud)

        response = self.client.delete(self._get_membership_url(membership))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def _get_valid_payload(self, cloud=None, project=None):
        cloud = cloud or factories.CloudFactory()
        project = project or structure_factories.ProjectFactory()
        return {
            'cloud': self._get_cloud_url(cloud),
            'project': self._get_project_url(project)
        }
