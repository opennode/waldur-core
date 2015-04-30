from __future__ import unicode_literals

from rest_framework import viewsets, decorators, response, status

from nodeconductor.template import models, serializers, TemplateError


class TemplateViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.Template.objects.all().prefetch_related('services')
    serializer_class = serializers.TemplateSerializer
    lookup_field = 'uuid'

    @decorators.detail_route(methods=['post'])
    def provision(self, request, uuid=None):
        template = self.get_object()
        serializer = serializers.TemplateServiceSerializer(
            data=request.data, many=True, context={'request': request, 'template': template})

        if serializer.is_valid():
            try:
                template.provision(serializer.initial_data, request=request)
            except TemplateError as e:
                return response.Response(
                    {'detail': "Failed to provision template", 'error': str(e)},
                    status=status.HTTP_409_CONFLICT)
            else:
                return response.Response(
                    {'detail': 'Provisioning for template services has been scheduled.'},
                    status=status.HTTP_200_OK)
        else:
            return response.Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
