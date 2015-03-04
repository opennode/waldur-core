
from rest_framework import serializers

from nodeconductor.iaas import models as iaas_models
from nodeconductor.iaas import serializers as iaas_serializers


class ImageSerializer(serializers.ModelSerializer):
    class Meta(object):
        model = iaas_models.Image
        fields = ('backend_id',)


class CloudSerializer(serializers.HyperlinkedModelSerializer):
    class Meta(object):
        model = iaas_models.Cloud
        fields = ('url', 'uuid', 'auth_url', 'name')
        lookup_field = 'uuid'


class IaasTemplateSerializer(serializers.ModelSerializer):
    service = CloudSerializer(read_only=True)
    flavor = iaas_serializers.FlavorSerializer(read_only=True)
    image = ImageSerializer(read_only=True)

    class Meta(object):
        model = iaas_models.ServiceTemplate
        fields = (
            'name', 'service', 'flavor', 'image', 'sla', 'sla_level', 'backup_schedule'
        )
