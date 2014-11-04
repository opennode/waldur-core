from rest_framework import status
from rest_framework import test
from rest_framework.reverse import reverse

from nodeconductor.cloud.tests import factories as cloud_factories
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

        cloud_factories.CloudProjectMembershipFactory(cloud=self.images['admin'].cloud, project=admined_project)
        cloud_factories.CloudProjectMembershipFactory(cloud=self.images['manager'].cloud, project=managed_project)

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

    def test_user_cannot_list_images_of_project_he_has_no_role_in(self):
        inaccessible_project = structure_factories.ProjectFactory()
        cloud_factories.CloudProjectMembershipFactory(
            cloud=self.images['inaccessible'].cloud, project=inaccessible_project)

        self._ensure_list_access_forbidden(self.users['no_role'], 'inaccessible')

    def test_user_cannot_list_images_not_allowed_for_any_project(self):
        for user in self.users.values():
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
        cloud_factories.CloudProjectMembershipFactory(
            cloud=self.images['inaccessible'].cloud, project=inaccessible_project)

        self._ensure_direct_access_forbidden(self.users['no_role'], 'inaccessible')

    def test_user_cannot_access_image_not_allowed_for_any_project(self):
        for user_role in self.users.values():
            self._ensure_direct_access_forbidden(user_role, 'inaccessible')

    # Creation tests
    def test_anonymous_user_cannot_create_image(self):
        for old_image in self.images.values():
            new_image = iaas_factories.ImageFactory(cloud=old_image.cloud)
            response = self.client.post(reverse('image-list'), self._get_valid_payload(new_image))
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticate_user_cannot_create_image(self):
        for user in self.users.values():
            self.client.force_authenticate(user=user)

            for old_image in self.images.values():
                new_image = iaas_factories.ImageFactory(cloud=old_image.cloud)
                response = self.client.post(reverse('image-list'), self._get_valid_payload(new_image))
                self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    # Mutation tests
    def test_anonymous_user_cannot_change_image(self):
        for image in self.images.values():
            data = self._get_valid_payload(image)
            response = self.client.put(self._get_image_url(image), data)
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_cannot_change_image_allowed_for_project_he_is_administrator_of(self):
        self.client.force_authenticate(self.users['admin'])
        image = self.images['admin']

        data = self._get_valid_payload(image)
        response = self.client.put(self._get_image_url(image), data)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_user_cannot_change_image_allowed_for_project_he_is_manager_of(self):
        self.client.force_authenticate(self.users['manager'])
        image = self.images['manager']

        data = self._get_valid_payload(image)
        response = self.client.put(self._get_image_url(image), data)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    # Deletion tests
    def test_anonymous_user_cannot_delete_image(self):
        for image in self.images.values():
            response = self.client.delete(self._get_image_url(image))
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_cannot_delete_image_allowed_for_project_he_is_administrator_of(self):
        self.client.force_authenticate(user=self.users['admin'])

        response = self.client.delete(self._get_image_url(self.images['admin']))
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_user_cannot_delete_image_allowed_for_project_he_is_manager_of(self):
        self.client.force_authenticate(user=self.users['manager'])

        response = self.client.delete(self._get_image_url(self.images['manager']))
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    # Helper methods
    def _get_image_url(self, image):
        return 'http://testserver' + reverse('image-detail', kwargs={'uuid': image.uuid})

    def _ensure_list_access_forbidden(self, user_role, image):
        self.client.force_authenticate(user=user_role)

        response = self.client.get(reverse('image-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        image_url = self._get_image_url(self.images[image])
        self.assertNotIn(image_url, [image['url'] for image in response.data])

    def _ensure_direct_access_forbidden(self, user_role, image):
        self.client.force_authenticate(user=user_role)

        response = self.client.get(self._get_image_url(self.images[image]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def _get_valid_payload(self, resource):
        return {
            'name': resource.name,
            'cloud': 'http://testserver' + reverse('cloud-detail',
                                                   kwargs={'uuid': resource.cloud.uuid}),
            'architecture': resource.architecture,
            'description': resource.description,
        }
