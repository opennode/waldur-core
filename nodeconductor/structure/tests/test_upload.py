import unittest
import tempfile

from django.utils.image import Image
from rest_framework import status
from rest_framework import test

from nodeconductor.structure.models import CustomerRole
from nodeconductor.structure.tests.factories import UserFactory, CustomerFactory
from nodeconductor.structure.tests.test_customer import UrlResolverMixin


def dummy_image():
    """
    Generate empty JPEG image in temporary file for testing
    """
    tmp_file = tempfile.NamedTemporaryFile(suffix='.jpg')
    image = Image.new('RGB', (100, 100))
    image.save(tmp_file)
    return open(tmp_file.name)


class ImageUploadTest(UrlResolverMixin, test.APITransactionTestCase):
    def setUp(self):
        self.staff = UserFactory(is_staff=True)
        self.owner = UserFactory()
        self.user = UserFactory()
        self.customer = CustomerFactory()
        self.customer.add_user(self.owner, CustomerRole.OWNER)
        self.url = self._get_customer_url(self.customer)

    def test_staff_can_upload_and_delete_customer_logo(self):
        self.client.force_authenticate(user=self.staff)

        with dummy_image() as image:
            self.assert_can_upload_image(image)
            self.assert_can_delete_image()

    def test_user_cannot_upload_logo_for_customer_he_is_not_owner_of(self):
        self.client.force_authenticate(user=self.user)

        with dummy_image() as image:
            self.assert_cannot_upload_image(image)

    @unittest.skip("Customer owner should be able to modify it's customer")
    def test_customer_owner_can_upload_and_delete_customer_logo(self):
        self.client.force_authenticate(user=self.owner)

        with dummy_image() as image:
            self.assert_can_upload_image(image)
            self.assert_can_delete_image()

    def assert_can_upload_image(self, image):
        response = self.client.patch(self.url, {'image': image}, format='multipart')
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertIsNotNone(response.data['image'])
        self.assertIn('size_50', response.data['image'])
        self.assertIn('size_100', response.data['image'])

    def assert_cannot_upload_image(self, image):
        response = self.client.patch(self.url, {'image': image}, format='multipart')
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def assert_can_delete_image(self):
        response = self.client.patch(self.url, {'image': None})
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertIsNone(response.data['image'])
