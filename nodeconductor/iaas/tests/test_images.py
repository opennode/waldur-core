from rest_framework import status
from rest_framework import test
from rest_framework.reverse import reverse

from nodeconductor.iaas.tests import factories as iaas_factories
from nodeconductor.structure.tests import factories as structure_factories
from nodeconductor.structure.models import ProjectRole


class ImagesApiPermissionTest(test.APISimpleTestCase):
    def setUp(self):
        self.users = {
            'admin': structure_factories.UserFactory(),
            'manager': structure_factories.UserFactory(),
            'no_role': structure_factories.UserFactory(),
        }

        self.images = {
            'admin': iaas_factories.ImageFactory(),
            'manager': iaas_factories.ImageFactory(),
            'inaccessible': iaas_factories.ImageFactory(),
        }

        admined_project = structure_factories.ProjectFactory()
        managed_project = structure_factories.ProjectFactory()

        admined_project.add_user(self.users['admin'], ProjectRole.ADMINISTRATOR)
        managed_project.add_user(self.users['manager'], ProjectRole.MANAGER)

        admined_project.clouds.add(self.images['admin'].cloud)
        managed_project.clouds.add(self.images['manager'].cloud)

    # List filtration tests
    def test_anonymous_user_cannot_list_images(self):
        response = self.client.get(reverse('image-list'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_can_list_images_of_project_he_is_administrator_of(self):
        self.client.force_authenticate(user=self.users['admin'])

        response = self.client.get(reverse('image-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        image_url = self._get_image_url(self.images['admin'])
        self.assertIn(image_url, [image['url'] for image in response.data])

    def test_user_can_list_images_of_project_he_is_manager_of(self):
        self.client.force_authenticate(user=self.users['manager'])

        response = self.client.get(reverse('image-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        image_url = self._get_image_url(self.images['manager'])
        self.assertIn(image_url, [image['url'] for image in response.data])

    def test_user_cannot_list_images_project_he_has_no_role_in(self):
        inaccessible_project = structure_factories.ProjectFactory()
        inaccessible_project.clouds.add(self.images['inaccessible'].cloud)

        self.client.force_authenticate(user=self.users['no_role'])

        response = self.client.get(reverse('image-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        image_url = self._get_image_url(self.images['inaccessible'])
        self.assertNotIn(image_url, [image['url'] for image in response.data])

    def test_user_cannot_list_images_not_allowed_for_any_project(self):
        for user in self.users.keys():
            self._ensure_list_access_forbidden(user, 'inaccessible')

    # Direct image access tests
    def test_anonymous_user_cannot_access_image(self):
        response = self.client.get(self._get_image_url(self.images['inaccessible']))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_can_access_image_of_project_he_is_administrator_of(self):
        self.client.force_authenticate(user=self.users['admin'])

        response = self.client.get(self._get_image_url(self.images['admin']))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_can_access_image_of_project_he_is_manager_of(self):
        self.client.force_authenticate(user=self.users['manager'])

        response = self.client.get(self._get_image_url(self.images['manager']))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_cannot_access_image_of_project_he_has_no_role_in(self):
        inaccessible_project = structure_factories.ProjectFactory()
        inaccessible_project.clouds.add(self.images['inaccessible'].cloud)

        self.client.force_authenticate(user=self.users['no_role'])

        response = self.client.get(self._get_image_url(self.images['inaccessible']))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_cannot_access_image_not_allowed_for_any_project(self):
        for user_role in self.users.keys():
            self._ensure_direct_access_forbidden(user_role, 'inaccessible')

    # Helper methods
    def _get_image_url(self, image):
        return 'http://testserver' + reverse('image-detail', kwargs={'uuid': image.uuid})

    def _ensure_list_access_forbidden(self, user_role, image):
        self.client.force_authenticate(user=self.users[user_role])

        response = self.client.get(reverse('image-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        image_url = self._get_image_url(self.images[image])
        self.assertNotIn(image_url, [image['url'] for image in response.data])

    def _ensure_direct_access_forbidden(self, user_role, image):
        self.client.force_authenticate(user=self.users[user_role])

        response = self.client.get(self._get_image_url(self.images[image]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)