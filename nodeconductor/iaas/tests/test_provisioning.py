from __future__ import unicode_literals

from django.core.urlresolvers import reverse
from rest_framework import status
from rest_framework import test

from nodeconductor.cloud.tests import factories as cloud_factories
from nodeconductor.iaas.tests import factories


class InstanceProvisioningTest(test.APISimpleTestCase):
    def setUp(self):
        self.instance_list_url = reverse('instance-list')

        self.cloud = cloud_factories.CloudFactory()
        self.template = factories.TemplateFactory()
        self.flavor = cloud_factories.FlavorFactory(cloud=self.cloud)

    # Positive tests
    def test_can_create_instance_without_volume_sizes(self):
        data = self.get_valid_data()
        del data['volume_sizes']
        response = self.client.post(self.instance_list_url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    # Negative tests
    # TODO: Validate whether flavor corresponds to chosen cloud type
    def test_cannot_create_instance_with_empty_template_name(self):
        data = self.get_valid_data()
        data['template'] = ''

        response = self.client.post(self.instance_list_url, data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertDictContainsSubset({'template': ['This field is required.']}, response.data)

    def test_cannot_create_instance_without_template_name(self):
        data = self.get_valid_data()
        del data['template']
        response = self.client.post(self.instance_list_url, data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertDictContainsSubset({'template': ['This field is required.']}, response.data)

    def test_cannot_create_instance_with_negative_volume_size(self):
        self.skipTest("Not implemented yet")

        data = self.get_valid_data()
        data['volume_size'] = -12

        response = self.client.post(self.instance_list_url, data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertDictContainsSubset({'volume_size': ['Ensure this value is greater than or equal to 1.']},
                                      response.data)

    def test_cannot_create_instance_with_invalid_volume_sizes(self):
        self.skipTest("Not implemented yet")

        data = self.get_valid_data()
        data['volume_sizes'] = 'gibberish'

        response = self.client.post(self.instance_list_url, data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertDictContainsSubset({'volume_sizes': ['Enter a whole number.']},
                                      response.data)

    # Helper methods
    def get_valid_data(self):
        return {
            # Cloud independent parameters
            'hostname': 'host1',
            'template': reverse('template-detail', kwargs={'uuid': self.template.uuid}),

            # Should not depend on cloud, instead represents an "aggregation" of templates
            'cloud': reverse('cloud-detail', kwargs={'uuid': self.cloud.uuid}),
            'volume_sizes': [10, 15, 10],
            'tags': set(),

            # Cloud dependent parameters
            'flavor': reverse('flavor-detail', kwargs={'uuid': self.flavor.uuid}),
        }
