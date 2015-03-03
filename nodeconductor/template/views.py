from __future__ import unicode_literals

from nodeconductor.core import viewsets
from nodeconductor.template import models
from nodeconductor.template import serializers


class TemplateViewSet(viewsets.CreateModelViewSet):
    queryset = models.Template.objects.all().prefetch_related('services')
    serializer_class = serializers.TemplateSerializer
    lookup_field = 'uuid'
