from __future__ import unicode_literals

from nodeconductor.core import viewsets
from nodeconductor.template.models import Template
from nodeconductor.template.serializers import TemplateSerializer


class TemplateViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Template.objects.all().prefetch_related('services')
    serializer_class = TemplateSerializer
    lookup_field = 'uuid'
