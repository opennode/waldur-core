from __future__ import unicode_literals

from rest_framework import serializers

from nodeconductor.template import get_template_services
from nodeconductor.template.models import Template, TemplateService


class TemplateServiceSerializer(serializers.ModelSerializer):
    def to_representation(self, instance):
        for service in get_template_services():
            if isinstance(instance, service):
                data = service._serializer(instance, context=self.context).to_representation(instance)
                data['service_type'] = instance.service_type
                return data

        return super(TemplateServiceSerializer, self).to_representation(instance)

    class Meta(object):
        model = TemplateService
        exclude = ('base_template',)


class TemplateSerializer(serializers.HyperlinkedModelSerializer):
    services = TemplateServiceSerializer(
        many=True, read_only=True)

    class Meta(object):
        model = Template
        fields = (
            'url', 'uuid', 'name',
            'description', 'icon_url', 'services',
            'is_active'
        )
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
        }
