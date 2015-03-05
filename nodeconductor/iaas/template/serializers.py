
from rest_framework import serializers

from nodeconductor.iaas.models import Cloud, Image, IaasTemplateService
from nodeconductor.iaas.serializers import FlavorSerializer


class CloudSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Cloud
        fields = ('url', 'uuid', 'auth_url', 'name')
        lookup_field = 'uuid'


class ImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Image
        fields = ('backend_id',)


class IaasTemplateServiceSerializer(serializers.ModelSerializer):
    service = CloudSerializer(read_only=True)
    flavor = FlavorSerializer(read_only=True)
    image = ImageSerializer(read_only=True)

    class Meta:
        model = IaasTemplateService
        fields = (
            'name', 'service', 'flavor', 'image', 'sla', 'sla_level', 'backup_schedule'
        )
