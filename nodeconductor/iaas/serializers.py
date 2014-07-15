from rest_framework import serializers

from nodeconductor.iaas import models


class InstanceCreateSerializer(serializers.HyperlinkedModelSerializer):
    class Meta(object):
        model = models.Instance
        fields = ('url', 'hostname', 'template', 'flavor')
        lookup_field = 'uuid'
        # TODO: Accept ip address count and volumes


class InstanceSerializer(serializers.HyperlinkedModelSerializer):
    cloud = serializers.HyperlinkedRelatedField(
        source='flavor.cloud',
        view_name='cloud-detail',
        lookup_field='uuid',
        read_only=True,
    )

    class Meta(object):
        model = models.Instance
        fields = ('url', 'hostname', 'template', 'cloud', 'flavor', 'state')
        lookup_field = 'uuid'
        # TODO: Render ip addresses and volumes


class TemplateSerializer(serializers.HyperlinkedModelSerializer):
    class Meta(object):
        model = models.Template
        fields = ('url', 'name')
        lookup_field = 'uuid'
