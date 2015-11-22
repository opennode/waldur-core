from django import forms

from rest_framework import serializers

from nodeconductor.openstack import models
from nodeconductor_templates.forms import TemplateForm
from nodeconductor_templates.serializers import BaseTemplateSerializer


class InstanceProvisionTemplateForm(TemplateForm):
    service = forms.ModelChoiceField(
        label="OpenStack service", queryset=models.OpenStackService.objects.all(), required=False)

    flavor = forms.ModelChoiceField(label="Flavor", queryset=models.Flavor.objects.all(), required=False)
    image = forms.ModelChoiceField(label="Image", queryset=models.Image.objects.all(), required=False)
    data_volume_size = forms.IntegerField(label='Data volume size', required=False)
    system_volume_size = forms.IntegerField(label='System volume size', required=False)

    class Meta(TemplateForm.Meta):
        fields = TemplateForm.Meta.fields + ('service', 'project', 'flavor', 'image', 'data_volume_size',
                                             'system_volume_size')

    class Serializer(BaseTemplateSerializer):
        service = serializers.HyperlinkedRelatedField(
            view_name='openstack-detail',
            queryset=models.OpenStackService.objects.all(),
            lookup_field='uuid',
            required=False,
        )
        flavor = serializers.HyperlinkedRelatedField(
            view_name='openstack-flavor-detail',
            lookup_field='uuid',
            queryset=models.Flavor.objects.all().select_related('settings'),
            required=False,
        )
        image = serializers.HyperlinkedRelatedField(
            view_name='openstack-image-detail',
            lookup_field='uuid',
            queryset=models.Image.objects.all().select_related('settings'),
            required=False,
        )
        data_volume_size = serializers.IntegerField(required=False)
        system_volume_size = serializers.IntegerField(required=False)

    @classmethod
    def get_serializer_class(cls):
        return cls.Serializer

    @classmethod
    def get_resource_model(cls):
        return models.Instance
