from __future__ import unicode_literals

from django.test import TestCase, RequestFactory
from rest_framework.serializers import ValidationError

from nodeconductor.iaas import serializers
from nodeconductor.iaas.tests import factories
from nodeconductor.structure.tests import factories as structure_factories


class InstanceCreateSerializerTest(TestCase):
    def setUp(self):
        user = structure_factories.UserFactory()
        self.serializer = serializers.InstanceCreateSerializer(context={'user': user})

    def test_instance_with_template_not_connected_to_cloud_raises_validation_error(self):
        attrs = {'template': factories.TemplateFactory(),
                 'project': structure_factories.ProjectFactory(),
                 'flavor': factories.FlavorFactory()}

        attrs['cloud_project_membership'] = factories.CloudProjectMembershipFactory(
            cloud=attrs['flavor'].cloud,
            project=attrs['project'],
        )

        with self.assertRaises(ValidationError) as er:
            self.serializer.validate(attrs)
            self.assertEquals(
                er.message, ["Template %s is not available on cloud %s" % (attrs['template'], attrs['flavor'].cloud)])

    def test_instance_with_flavor_and_template_connected_to_different_clouds_raises_validation_error(self):
        attrs = {'template': factories.TemplateFactory(),
                 'project': structure_factories.ProjectFactory(),
                 'flavor': factories.FlavorFactory()}

        factories.ImageFactory(template=attrs['template'])
        attrs['cloud_project_membership'] = factories.CloudProjectMembershipFactory(
            cloud=attrs['flavor'].cloud,
            project=attrs['project'],
        )

        with self.assertRaises(ValidationError) as er:
            self.serializer.validate(attrs)
            self.assertEquals(
                er.message, ["Template %s is not available on cloud %s" % (attrs['template'], attrs['flavor'].cloud)])


class InstanceCreateSerializer2Test(TestCase):
    def setUp(self):
        self.template = factories.TemplateFactory()
        self.flavor = factories.FlavorFactory()
        self.project = structure_factories.ProjectFactory()
        self.ssh_public_key = structure_factories.SshPublicKeyFactory()
        self.membership = factories.CloudProjectMembershipFactory(
            cloud=self.flavor.cloud,
            project=self.project,
        )

        factories.ImageFactory(template=self.template, cloud=self.flavor.cloud)
        factories.FloatingIPFactory(status='DOWN', cloud_project_membership=self.membership, address='10.10.10.10')

    def test_external_ips_must_be_a_list(self):
        invalid_values = (123, 12.3, 'test')

        for invalid_value in invalid_values:
            errors = self.get_deserialization_errors(external_ips=invalid_value)
            self.assertDictContainsSubset(
                {'external_ips': ['Expected a list of items but got type "%s".' % type(invalid_value).__name__]},
                errors
            )

    def test_external_ips_must_contain_less_then_two_items(self):
        errors = self.get_deserialization_errors(external_ips=['127.0.0.1', '10.10.10.10'])
        self.assertDictContainsSubset({'external_ips': ['Only 1 ip address is supported.']}, errors)

    def test_external_ips_must_contain_valid_ip_address(self):
        errors = self.get_deserialization_errors(external_ips=['foobar'])
        self.assertDictContainsSubset({'external_ips': ['Enter a valid IPv4 address.']}, errors)

    def test_external_ips_set_to_empty_list_deserializes_to_none(self):
        instance = self.deserialize_instance(external_ips=[])
        self.assertIsNone(instance.external_ips)

    def test_external_ips_set_a_single_valid_ip_deserializes_to_this_ip(self):
        instance = self.deserialize_instance(external_ips=['10.10.10.10'])
        self.assertEqual('10.10.10.10', instance.external_ips)

    def get_deserialization_errors(self, **kwargs):
        serializer = serializers.InstanceCreateSerializer(data=kwargs)
        serializer.is_valid()
        errors = serializer.errors
        return errors

    def deserialize_instance(self, **kwargs):
        data = self.get_valid_data()
        data.update(**kwargs)

        serializer = serializers.InstanceCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid(), 'Instance must be valid, errors: %r' % serializer.errors)
        return serializer.save()

    # TODO: Add the same to InstanceCreateSerializerTest

    def get_valid_data(self):
        return {
            'name': 'host1',
            'description': 'description1',

            'project': structure_factories.ProjectFactory.get_url(self.project),

            'template': factories.TemplateFactory.get_url(self.template),

            'external_ips': [],

            'flavor': factories.FlavorFactory.get_url(self.flavor),
            'ssh_public_key': structure_factories.SshPublicKeyFactory.get_url(self.ssh_public_key)
        }


class InstanceSerializerTest(TestCase):
    def test_internal_ips_set_to_null_renders_as_empty_list(self):
        data = self.serialize_instance(internal_ips=None)
        self.assertDictContainsSubset({'internal_ips': []}, data)

    def test_internal_ips_set_to_address_renders_as_list_of_a_single_address(self):
        data = self.serialize_instance(internal_ips='10.0.10.10')
        self.assertDictContainsSubset({'internal_ips': ['10.0.10.10']}, data)

    def test_external_ips_set_to_null_renders_as_empty_list(self):
        data = self.serialize_instance(external_ips=None)
        self.assertDictContainsSubset({'external_ips': []}, data)

    def test_external_ips_set_to_address_renders_as_list_of_a_single_address(self):
        data = self.serialize_instance(external_ips='8.8.8.8')
        self.assertDictContainsSubset({'external_ips': ['8.8.8.8']}, data)

    def serialize_instance(self, **kwargs):
        instance = factories.InstanceFactory(**kwargs)
        factory = RequestFactory()
        request = factory.post(factories.InstanceFactory.get_url(instance))
        serializer = serializers.InstanceSerializer(instance=instance, context={'request': request})
        data = serializer.data
        return data


class CloudProjectMembershipQuotaSerializerTest(TestCase):
    def test_cloud_project_membership_quota_serializer_accepts_positive_values(self):
        data = {
            'max_instances': 12,
            'vcpu': 20,
            'storage': 40 * 1024,
            'ram': 20 * 1024,
        }
        serializer = serializers.CloudProjectMembershipQuotaSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(data, serializer.data)

    def test_cloud_project_membership_quota_serializer_fails_on_negative_values(self):
        data = {
            'max_instances': -1,
            'vcpu': -1,
            'storage': -1,
            'ram': -1,
        }
        serializer = serializers.CloudProjectMembershipQuotaSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_cloud_project_membership_quota_serializer_fails_on_symbolic_values(self):
        data = {
            'max_instances': 'lalala',
            'vcpu': 'lalala',
            'storage': 'lalala',
            'ram': 'lalala',
        }
        serializer = serializers.CloudProjectMembershipQuotaSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_cloud_project_membership_quota_serializer_ignores_unsupported_fields(self):
        data = {
            'some_strange_quota_name': 1,
        }
        serializer = serializers.CloudProjectMembershipQuotaSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertTrue('some_strange_quota_name' not in serializer.data)


class ExternalNetworkSerializerTest(TestCase):
    def test_external_network_serializer_accepts_valid_values(self):
        data = {
            'vlan_id': '2007',
            'network_ip': '10.7.122.0',
            'network_prefix': 26,
            'ips_count': 6
        }
        serializer = serializers.ExternalNetworkSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(data, serializer.data)

    def test_external_network_serializer_fail_with_vlan_and_vxlan_ids(self):
        data = {
            'vlan_id': 1234,
            'vxlan_id': 2008,
            'network_ip': '10.7.122.0.125',
            'network_prefix': 15,
            'ips_count': 6
        }
        serializer = serializers.ExternalNetworkSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_external_network_serializer_fail_without_vlan_and_vxlan_ids(self):
        data = {
            'network_ip': '10.7.122.0.125',
            'network_prefix': 'ab',
            'ips_count': 'cd'
        }
        serializer = serializers.ExternalNetworkSerializer(data=data)
        self.assertFalse(serializer.is_valid())
