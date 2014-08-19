from __future__ import unicode_literals

from rest_framework import serializers

from nodeconductor.structure import models


class ProjectSerializer(serializers.HyperlinkedModelSerializer):
    class Meta(object):
        model = models.Project
        fields = ('url', 'name')
        lookup_field = 'uuid'


class ProjectGroupSerializer(serializers.HyperlinkedModelSerializer):
    class Meta(object):
        model = models.ProjectGroup
        fields = ('url', 'name')
        lookup_field = 'uuid'
