from __future__ import unicode_literals

from rest_framework import serializers, exceptions

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

    def run_validation(self, data):
        services = {service.service_type: service for service in get_template_services()}
        try:
            service_type = data['service_type']
            service = services[service_type]
        except KeyError:
            raise exceptions.ValidationError(
                {'service_type': "Unsupported service type %s" % data.get('service_type')})

        cur_service = service.objects.get(template=self.context.get('template'))
        cur_serializer = service._create_serializer(cur_service, context=self._context)

        for field in cur_serializer.fields:
            if hasattr(cur_service, field) and field not in data:
                value = cur_serializer.data[field]
                if value is not None:
                    data[field] = value

        new_serializer = service._create_serializer(data=data)
        validated_data = new_serializer.run_validation(data)
        return validated_data

    class Meta(object):
        model = TemplateService
        exclude = ('template',)


class TemplateSerializer(serializers.HyperlinkedModelSerializer):
    services = TemplateServiceSerializer(
        many=True, read_only=True)

    class Meta(object):
        model = Template
        lookup_field = 'uuid'
        fields = (
            'url', 'uuid', 'name',
            'description', 'icon_url', 'services',
            'is_active'
        )
