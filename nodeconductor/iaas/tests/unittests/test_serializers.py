from django.test import TestCase
from django.core.exceptions import ValidationError
from django.http import Http404

from nodeconductor.cloud import models as cloud_models
from nodeconductor.cloud.tests import factories as cloud_factories
from nodeconductor.iaas import serializers
from nodeconductor.iaas.tests import factories
from nodeconductor.cloud import models as cloud_models
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
        attrs = {'security_groups': [{'name': cloud_factories.SecurityGroupFactory().name}]}
        self.serializer.validate_security_groups(attrs, attr_name)
        self.assertIn('security_groups', attrs)

    def test_validate_ssh_public_key(self):
        # wrong public key
        attrs = {'ssh_public_key': factories.SshPublicKeyFactory()}
        attr_name = 'ssh_public_key'
        self.assertRaises(Http404, lambda: self.serializer.validate_ssh_public_key(attrs, attr_name))
        # right public key
        self.serializer.user = attrs['ssh_public_key'].user
        self.serializer.validate_ssh_public_key(attrs, attr_name)
        self.assertIn(attr_name, attrs)

