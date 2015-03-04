
from rest_framework import serializers

from nodeconductor.template import models
from nodeconductor.template.utils import get_template_services


class TemplateServiceSerializer(serializers.ModelSerializer):

    def to_native(self, obj):
        for service in get_template_services():
            if isinstance(obj, service.get_model()):
                return service.get_serializer()(obj, context=self.context).to_native(obj)

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
