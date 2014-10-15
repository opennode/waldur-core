from django.test import TestCase
from django.core.exceptions import ValidationError

from nodeconductor.iaas import serializers
from nodeconductor.cloud import models as cloud_models


class InstanceCreateSerializerTest(TestCase):

    def setUp(self):
        self.serializer = serializers.InstanceCreateSerializer()

    def test_validate_security_groups(self):
        # if security groups is none - they have to be deleted from attrs
        attrs = {'security_groups': None}
        attr_name = 'security_groups'
        self.serializer.validate_security_groups(attrs, attr_name)
        self.assertEqual(len(attrs), 0)
        # all ok:
        attrs = {'security_groups': [{'name': cloud_models.SecurityGroups.groups_names[0]}]}
        self.serializer.validate_security_groups(attrs, attr_name)
        self.assertIn('security_groups', attrs)


class InstanceSecurityGroupSerializerTest(TestCase):

    def setUp(self):
        self.serializer = serializers.InstanceSecurityGroupSerializer()

    def test_validate_name(self):
        # if security groups is not in cloud security groups list - ValidationError have to be raised
        attrs = {'security_groups': [{'name': 'some_random_name'}]}
        attr_name = 'security_groups'
        self.assertRaises(ValidationError, lambda: self.serializer.validate_name(attrs, attr_name))
