from __future__ import unicode_literals

from django.core.urlresolvers import reverse
from mock import patch
from rest_framework import status
from rest_framework import test

from nodeconductor.cloud import models
from nodeconductor.cloud.tests import factories
from nodeconductor.structure.models import CustomerRole
from nodeconductor.structure.models import ProjectRole
from nodeconductor.structure.tests import factories as structure_factories


# noinspection PyMethodMayBeStatic
class UrlResolverMixin(object):

    def _get_project_url(self, project):
        return 'http://testserver' + reverse('project-detail', kwargs={'uuid': project.uuid})

    def _get_cloud_url(self, cloud):
        return 'http://testserver' + reverse('cloud-detail', kwargs={'uuid': cloud.uuid})


class CloudProjectMembershipCreateDeleteTest(UrlResolverMixin, test.APISimpleTestCase):

    def setUp(self):
        self.owner = structure_factories.UserFactory(is_staff=True, is_superuser=True)
        self.customer = structure_factories.CustomerFactory()
        self.customer.add_user(self.owner, CustomerRole.OWNER)

        self.project = structure_factories.ProjectFactory(customer=self.customer)
        self.cloud = factories.CloudFactory(customer=self.customer)

    def test_memebership_creation(self):
        self.client.force_authenticate(self.owner)
        url = factories.CloudProjectMembershipFactory.get_list_url()
        data = {
            'cloud': self._get_cloud_url(self.cloud),
            'project': self._get_project_url(self.project)
        }

        with patch('nodeconductor.cloud.tasks.initial_push_cloud_membership.delay') as mocked_task:
            response = self.client.post(url, data)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            membership = models.CloudProjectMembership.objects.get(project=self.project, cloud=self.cloud)
            mocked_task.assert_called_with(membership.pk)


# XXX: this have to be reworked to permissions test

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

        # that has 2 users connected: admin and manager
        self.connected_project = structure_factories.ProjectFactory(customer=self.customer)
        self.connected_project.add_user(self.users['admin'], ProjectRole.ADMINISTRATOR)
        self.connected_project.add_user(self.users['manager'], ProjectRole.MANAGER)

        # has defined a cloud and connected cloud to a project
        self.cloud = factories.CloudFactory(customer=self.customer)
        factories.CloudProjectMembershipFactory(project=self.connected_project, cloud=self.cloud)

        # the customer also has another project with users but without a permission link
        self.not_connected_project = structure_factories.ProjectFactory(customer=self.customer)
        self.not_connected_project.add_user(self.users['not_connected'], ProjectRole.ADMINISTRATOR)
        self.not_connected_project.save()

    def test_anonymous_user_cannot_grant_cloud_to_project(self):
        response = self.client.post(reverse('cloudproject_membership-list'), self._get_valid_payload())
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_can_connect_cloud_and_project_he_owns(self):
        user = self.users['owner']
        self.client.force_authenticate(user=user)

        cloud = factories.CloudFactory(customer=self.customer)
        project = structure_factories.ProjectFactory(customer=self.customer)

        payload = self._get_valid_payload(cloud, project)

        response = self.client.post(reverse('cloudproject_membership-list'), payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_user_cannot_connect_new_cloud_and_project_if_he_is_project_admin(self):
        for user_role in ['admin', 'manager']:
            user = self.users[user_role]
            self.client.force_authenticate(user=user)

            cloud = factories.CloudFactory(customer=self.customer)
            project = self.connected_project
            payload = self._get_valid_payload(cloud, project)

            response = self.client.post(reverse('cloudproject_membership-list'), payload)
            # the new cloud should not be visible to the user
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertDictContainsSubset(
                {'cloud': ['Invalid hyperlink - object does not exist.']}, response.data)

    def test_user_cannot_revoke_cloud_and_project_permission_if_he_is_project_admin(self):
        user = self.users['manager']
        self.client.force_authenticate(user=user)

        project = self.connected_project
        cloud = self.cloud
        membership = factories.CloudProjectMembershipFactory(project=project, cloud=cloud)

        url = factories.CloudProjectMembershipFactory.get_url(membership)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def _get_valid_payload(self, cloud=None, project=None):
        cloud = cloud or factories.CloudFactory()
        project = project or structure_factories.ProjectFactory()
        return {
            'cloud': self._get_cloud_url(cloud),
            'project': self._get_project_url(project)
        }
