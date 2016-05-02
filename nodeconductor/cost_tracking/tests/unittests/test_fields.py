from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from nodeconductor.cost_tracking.fields import ResourceTypeField
from nodeconductor.openstack.models import Instance
from nodeconductor.structure import SupportedServices


class TestResourceTypeField(TestCase):
    def setUp(self):
        self.field = ResourceTypeField()
        self.content_type = ContentType.objects.get_for_model(Instance)
        self.name = SupportedServices.get_name_for_model(Instance)

    def test_content_type_serialized_to_model_name(self):
        self.assertEqual(self.field.to_representation(self.content_type), self.name)

    def test_model_name_deserialized_to_content_type(self):
        self.assertEqual(self.field.to_internal_value(self.name), self.content_type)

    def test_resource_content_type_is_valid_choice(self):
        self.assertIn(self.content_type, dict(self.field.get_choices()).keys())
