from __future__ import unicode_literals

from django.core.urlresolvers import reverse
from django.utils import unittest
from rest_framework import status
from rest_framework import test

from nodeconductor.cloud.tests import factories as factories
from nodeconductor.structure.models import ProjectRole
from nodeconductor.structure.tests import factories as structure_factories


@unittest.skip("Model inheritance & object level permissions haven't been married yet")
class CloudPermissionTest(test.APISimpleTestCase):
    def setUp(self):
        self.user = structure_factories.UserFactory.create()
        self.client.force_authenticate(user=self.user)

        admined_project = structure_factories.ProjectFactory()
        managed_project = structure_factories.ProjectFactory()
        
        admined_project.add_user(self.user, ProjectRole.ADMINISTRATOR)
        managed_project.add_user(self.user, ProjectRole.MANAGER)

        self.admined_cloud = factories.CloudFactory()
        self.managed_cloud = factories.CloudFactory()

        admined_project.clouds.add(self.admined_cloud)
        managed_project.clouds.add(self.managed_cloud)

    def test_user_can_list_clouds_of_projects_he_is_administrator_of(self):
        response = self.client.get(reverse('cloud-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        cloud_url = self._get_cloud_url(self.admined_cloud)
        self.assertIn(cloud_url, [instance['url'] for instance in response.data])

    def test_user_can_list_clouds_of_projects_he_is_manager_of(self):
        response = self.client.get(reverse('cloud-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        cloud_url = self._get_cloud_url(self.managed_cloud)
        self.assertIn(cloud_url, [instance['url'] for instance in response.data])

    def test_user_cannot_list_clouds_of_projects_he_has_no_role_in(self):
        inaccessible_cloud = factories.CloudFactory()

        response = self.client.get(reverse('cloud-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        cloud_url = self._get_cloud_url(inaccessible_cloud)
        self.assertNotIn(cloud_url, [instance['url'] for instance in response.data])

    def test_user_can_access_cloud_allowed_for_project_he_is_administrator_of(self):
        response = self.client.get(self._get_cloud_url(self.admined_cloud))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_can_access_cloud_allowed_for_project_he_is_manager_of(self):
        response = self.client.get(self._get_cloud_url(self.managed_cloud))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_cannot_access_cloud_allowed_for_project_he_has_no_role_in(self):
        inaccessible_cloud = factories.CloudFactory()
        inaccessible_project = structure_factories.ProjectFactory()
        inaccessible_project.clouds.add(inaccessible_cloud)

        response = self.client.get(self._get_cloud_url(inaccessible_cloud))
        # 404 is used instead of 403 to hide the fact that the resource exists at all
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_cannot_access_cloud_not_allowed_for_any_project(self):
        inaccessible_cloud = factories.CloudFactory()

        response = self.client.get(self._get_cloud_url(inaccessible_cloud))
        # 404 is used instead of 403 to hide the fact that the resource exists at all
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def _get_cloud_url(self, cloud):
        return 'http://testserver' + reverse('cloud-detail', kwargs={'uuid': cloud.uuid})
