from __future__ import unicode_literals

# from django.core.exceptions import ValidationError
from django.test import TestCase, RequestFactory
from rest_framework.serializers import ValidationError

from nodeconductor.iaas import serializers
from nodeconductor.iaas.tests import factories
from nodeconductor.template.tests import factories as template_factories
from nodeconductor.template import serializers as template_serializers
from nodeconductor.structure.tests import factories as structure_factories


class InstanceCreateSerializerTest(TestCase):
    def setUp(self):
        user = structure_factories.UserFactory()
        self.serializer = serializers.InstanceCreateSerializer(context={'user': user})

    def test_instance_with_template_not_connected_to_cloud_raises_validation_error(self):
        attrs = {'template': factories.TemplateFactory(),
                 'project': structure_factories.ProjectFactory(),
                 'flavor': factories.FlavorFactory()}

        factories.CloudProjectMembershipFactory(
            cloud=attrs['flavor'].cloud,
            project=attrs['project']
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
        factories.CloudProjectMembershipFactory(
            cloud=attrs['flavor'].cloud,
            project=attrs['project']
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
        self.ssh_public_key = factories.SshPublicKeyFactory()
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
            'hostname': 'host1',
            'description': 'description1',

            'project': structure_factories.ProjectFactory.get_url(self.project),

            'template': factories.TemplateFactory.get_url(self.template),

            'external_ips': [],

            'flavor': factories.FlavorFactory.get_url(self.flavor),
            'ssh_public_key': factories.SshPublicKeyFactory.get_url(self.ssh_public_key)
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

# TODO: uncomment this after template migrations to drf3

# class IaasTemplateServiceTest(TestCase):

#     def setUp(self):
#         self.cloud = factories.CloudFactory()
#         self.flavor = factories.FlavorFactory(cloud=self.cloud)
#         self.image = factories.ImageFactory(cloud=self.cloud)
#         self.template = template_factories.TemplateFactory()
#         self.iaas_template_service = factories.IaasTemplateServiceFactory(
#             template=self.template,
#             service=self.cloud,
#             flavor=self.flavor,
#             image=self.image)

#     def test_create_template_service(self):
#         iaas_template_service = self.template.services.first()
#         self.assertIsNotNone(iaas_template_service)
#         self.assertIsInstance(iaas_template_service, factories.IaasTemplateServiceFactory._meta.model)
#         self.assertEqual(iaas_template_service.service, self.cloud)

#     def test_template_serializer_returns_proper_service_type(self):
#         serializer = template_serializers.TemplateSerializer(instance=self.template)
#         service_type = serializer.data['services'][0].get('service_type')
#         self.assertEqual(service_type, 'IaaS')
