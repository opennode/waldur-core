
from rest_framework import serializers

from nodeconductor.template import get_template_services
from nodeconductor.template.models import Template, TemplateService


class TemplateServiceSerializer(serializers.ModelSerializer):

    def to_native(self, obj):
        for service in get_template_services():
            if isinstance(obj, service):
                data = service._serializer(obj, context=self.context).to_native(obj)
                data['service_type'] = obj.service_type
                return data

        return super(TemplateServiceSerializer, self).to_native(obj)

    class Meta(object):
        model = TemplateService
        exclude = ('template',)


class TemplateSerializer(serializers.HyperlinkedModelSerializer):
    services = TemplateServiceSerializer(
        many=True, required=True, allow_add_remove=True, read_only=False)

    class Meta(object):
        model = Template
        lookup_field = 'uuid'
        fields = (
            'url', 'uuid', 'name',
            'description', 'icon_url', 'services',
            'is_active'
        )
