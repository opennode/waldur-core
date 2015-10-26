import mock

from django.db import models
from django.test import TestCase
from rest_framework import serializers

from nodeconductor.structure.serializers import ResourceProvisioningMetadata


class ResourceProvisioningMetadataTest(TestCase):
    def get_serializer(self):
        class Image(models.Model):
            name = models.CharField(max_length=100)

        class VirtualMachine(models.Model):
            STATE_CHOICES = (
                (1, 'Ready'),
                (2, 'Erred'),
            )

            name = models.CharField(max_length=100)
            description = models.TextField()

            state = models.IntegerField(choices=STATE_CHOICES)
            image = models.ForeignKey(Image)

        class VirtualMachineSerializer(serializers.ModelSerializer):
            class Meta:
                model = VirtualMachine
                fields = ('name', 'description', 'state', 'image')
                read_only_fields = ('name',)

        return VirtualMachineSerializer()

    def test_read_only_options_are_skipped(self):
        options = ResourceProvisioningMetadata()

        serializer = self.get_serializer()
        serializer_info = options.get_serializer_info(serializer)

        self.assertIn('description', serializer_info)
        self.assertNotIn('name', serializer_info)

    def test_choices_for_related_fields_are_not_exposed(self):
        options = ResourceProvisioningMetadata()

        serializer = self.get_serializer()
        serializer_info = options.get_serializer_info(serializer)

        self.assertIn('choices', serializer_info['state'])
        self.assertNotIn('choices', serializer_info['image'])
