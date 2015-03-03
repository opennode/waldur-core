from rest_framework import serializers

from nodeconductor.template import models
from nodeconductor.iaas import models as iaas_models
from nodeconductor.iaas import serializers as iaas_serializers


class ImageSerializer(serializers.ModelSerializer):
    class Meta(object):
        model = iaas_models.Image
        fields = ('backend_id',)


class InstanceSerializer(serializers.HyperlinkedModelSerializer):
    class Meta(object):
        model = iaas_models.Instance
        fields = ('url', 'uuid')
        lookup_field = 'uuid'


class TemplateServiceIaaSSerializer(serializers.ModelSerializer):
    service = InstanceSerializer(read_only=True)
    flavor = iaas_serializers.FlavorSerializer(read_only=True)
    image = ImageSerializer(read_only=True)

    class Meta(object):
        model = models.TemplateServiceIaaS
        fields = (
            'name', 'service', 'flavor', 'image', 'sla', 'sla_level', 'backup_schedule'
        )


class TemplateServiceSerializer(serializers.ModelSerializer):

    def to_native(self, obj):
        if isinstance(obj, models.TemplateServiceIaaS):
            return TemplateServiceIaaSSerializer(obj, context=self.context).to_native(obj)

        return super(TemplateServiceSerializer, self).to_native(obj)

    class Meta(object):
        model = models.TemplateService


class TemplateSerializer(serializers.HyperlinkedModelSerializer):
    services = TemplateServiceSerializer(
        many=True, required=True, allow_add_remove=True, read_only=False)

    class Meta(object):
        model = models.Template
        lookup_field = 'uuid'
        fields = (
            'url', 'uuid', 'name',
            'description', 'icon_url', 'services',
            'is_active'
        )
