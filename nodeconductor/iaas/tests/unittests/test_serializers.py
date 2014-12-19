from django.core.exceptions import ValidationError
from django.test import TestCase

from nodeconductor.iaas import serializers
from nodeconductor.iaas.tests import factories
from nodeconductor.structure.tests import factories as structure_factories


class InstanceCreateSerializerTest(TestCase):
    def setUp(self):
        user = structure_factories.UserFactory()
        self.serializer = serializers.InstanceCreateSerializer(context={'user': user})

    def test_validate_security_groups(self):
        # if security groups is none - they have to be deleted from attrs
        attrs = {'security_groups': None}
        attr_name = 'security_groups'
        self.serializer.validate_security_groups(attrs, attr_name)
        self.assertEqual(len(attrs), 0)
        # all ok:
        attrs = {'security_groups': [{'name': factories.SecurityGroupFactory().name}]}
        self.serializer.validate_security_groups(attrs, attr_name)
        self.assertIn('security_groups', attrs)

    def test_instance_with_template_not_connected_to_cloud_raises_validation_error(self):
        attrs = {'template': factories.TemplateFactory(),
                 'project': structure_factories.ProjectFactory(),
                 'flavor': factories.FlavorFactory()}

        factories.CloudProjectMembershipFactory(
            cloud=attrs['flavor'].cloud,
            project=attrs['project']
        )

        with self.assertRaisesRegexp(ValidationError,
                                     "Template %s is not available on cloud %s" % (attrs['template'],
                                                                                   attrs['flavor'].cloud)):
            self.serializer.validate(attrs)

    def test_instance_with_flavor_and_template_connected_to_different_clouds_raises_validation_error(self):
        attrs = {'template': factories.TemplateFactory(),
                 'project': structure_factories.ProjectFactory(),
                 'flavor': factories.FlavorFactory()}

        factories.ImageFactory(template=attrs['template'])
        factories.CloudProjectMembershipFactory(
            cloud=attrs['flavor'].cloud,
            project=attrs['project']
        )

        with self.assertRaisesRegexp(ValidationError,
                                     "Template %s is not available on cloud %s" % (attrs['template'],
                                                                                   attrs['flavor'].cloud)):
            self.serializer.validate(attrs)
