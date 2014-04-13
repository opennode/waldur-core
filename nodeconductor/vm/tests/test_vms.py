from rest_framework import status
from rest_framework import test

from django.core.urlresolvers import reverse


class VmProvisioningTest(test.APISimpleTestCase):
    def setUp(self):
        self.vm_list_url = reverse('vm-list')

    # Positive tests
    def test_can_create_vm_without_volume_size(self):
        data = self.get_valid_data()
        del data['volume_size']
        response = self.client.post(self.vm_list_url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    # Negavite tests
    def test_cannot_create_vm_with_empty_image_name(self):
        data = self.get_valid_data()
        data['image'] = ''

        response = self.client.post(self.vm_list_url, data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertDictContainsSubset({'image': [u'This field is required.']}, response.data)

    def test_cannot_create_vm_without_image_name(self):
        data = self.get_valid_data()
        del data['image']
        response = self.client.post(self.vm_list_url, data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertDictContainsSubset({'image': [u'This field is required.']}, response.data)

    def test_cannot_create_vm_with_negative_volume_size(self):
        data = self.get_valid_data()
        data['volume_size'] = -12

        response = self.client.post(self.vm_list_url, data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertDictContainsSubset({'volume_size': [u'Ensure this value is greater than or equal to 1.']},
                                      response.data)

    def test_cannot_create_vm_with_invalid_volume_size(self):
        data = self.get_valid_data()
        data['volume_size'] = 'gibberish'

        response = self.client.post(self.vm_list_url, data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertDictContainsSubset({'volume_size': [u'Enter a whole number.']},
                                      response.data)

    # TODO: Check for requested volume missing
    # TODO: Check for requested volume minimum size being greater then requested volume_size

    # Helper methods
    def get_valid_data(self):
        return {
            'image': 'Centos-6.5',
            'volume_size': 10,
        }
