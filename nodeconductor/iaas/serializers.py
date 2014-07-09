from rest_framework import serializers

from nodeconductor.iaas import models


class CloudSerializer(serializers.HyperlinkedModelSerializer):
    class Meta(object):
        model = models.Cloud
        fields = ('url', 'name', 'type')
        lookup_field = 'uuid'


class FlavorSerializer(serializers.HyperlinkedModelSerializer):
    class Meta(object):
        model = models.Flavor
        fields = ('url', 'name')
        lookup_field = 'uuid'


class InstanceCreateSerializer(serializers.HyperlinkedModelSerializer):
    class Meta(object):
        model = models.Instance
        fields = ('url', 'hostname', 'template', 'cloud', 'flavor')
        lookup_field = 'uuid'
        # TODO: Accept ip address count and volumes


class InstanceSerializer(serializers.HyperlinkedModelSerializer):
    class Meta(object):
        model = models.Instance
        fields = ('url', 'hostname', 'cloud', 'flavor')
        lookup_field = 'uuid'
        # TODO: Render ip addresses and volumes


class TemplateSerializer(serializers.HyperlinkedModelSerializer):
    class Meta(object):
        model = models.Template
        fields = ('url', 'name')
        lookup_field = 'uuid'
