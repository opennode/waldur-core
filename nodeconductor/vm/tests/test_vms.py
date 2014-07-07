from django.core.urlresolvers import reverse
from rest_framework import status
from rest_framework import test

from nodeconductor.vm.tests import factories


# TODO: Rename to test_instances or test_provisioning

class InstanceProvisioningTest(test.APISimpleTestCase):
    def setUp(self):
        self.instance_list_url = reverse('instance-list')

        self.cloud = factories.CloudFactory()
        self.template = factories.TemplateFactory()
        self.flavor = factories.FlavorFactory(cloud=self.cloud)

    # Positive tests
    def test_can_create_vm_without_volume_sizes(self):
        data = self.get_valid_data()
        del data['volume_sizes']
        response = self.client.post(self.instance_list_url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    # Negative tests
    # TODO: Validate whether flavor corresponds to chosen cloud type
    def test_cannot_create_vm_with_empty_template_name(self):
        data = self.get_valid_data()
        data['template'] = ''

        response = self.client.post(self.instance_list_url, data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertDictContainsSubset({'template': [u'This field is required.']}, response.data)

    def test_cannot_create_vm_without_template_name(self):
        data = self.get_valid_data()
        del data['template']
        response = self.client.post(self.instance_list_url, data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertDictContainsSubset({'template': [u'This field is required.']}, response.data)

    def test_cannot_create_vm_with_negative_volume_size(self):
        self.skipTest("Not implemented yet")

        data = self.get_valid_data()
        data['volume_size'] = -12

        response = self.client.post(self.instance_list_url, data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertDictContainsSubset({'volume_size': [u'Ensure this value is greater than or equal to 1.']},
                                      response.data)

    def test_cannot_create_vm_with_invalid_volume_sizes(self):
        self.skipTest("Not implemented yet")

        data = self.get_valid_data()
        data['volume_sizes'] = 'gibberish'

        response = self.client.post(self.instance_list_url, data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertDictContainsSubset({'volume_sizes': [u'Enter a whole number.']},
                                      response.data)

    # Helper methods
    def get_valid_data(self):
        return {
            # Cloud independent parameters
            'hostname': 'host1',
            'template': reverse('template-detail', kwargs={'pk': self.template.pk}),

            # Should not depend on cloud, instead represents an "aggregation" of templates
            'cloud': reverse('cloud-detail', kwargs={'pk': self.cloud.pk}),
            'volume_sizes': [10, 15, 10],
            'tags': set(),

            # Cloud dependent parameters
            'flavor': reverse('flavor-detail', kwargs={'pk': self.flavor.pk}),
        }
