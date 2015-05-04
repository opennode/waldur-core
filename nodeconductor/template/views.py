from __future__ import unicode_literals

from rest_framework import viewsets, decorators, response, status

from nodeconductor.template import models, serializers, TemplateProvisionError


class TemplateViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.Template.objects.all().prefetch_related('services')
    serializer_class = serializers.TemplateSerializer
    lookup_field = 'uuid'

    @decorators.detail_route(methods=['post'])
    def provision(self, request, uuid=None):
        """ It accepts an empty POST or a list with redefined services' data must be supplied.
            Example post data:
            [
                {
                    "name": "Production VM",
                    "service": "http://example.com/api/clouds/b3870fbd57d94901811bec9bae6a20c2/",
                    "image": "d15dc2c4-25d6-4150-93fe-a412499298d8",
                    "backup_schedule": "0 10 * * *",
                    "data_volume_size": 1024,
                    "service_type": "IaaS",
                },
                {
                    "name": "Main Jira",
                    "service_type": "JIRA",
                },
            ]

            Provision options will be taken from a template instance unless redefined here.
            Additional options required for provisioning could be passed according to
            specific template service create serializer.
        """
        template = self.get_object()
        serializer = serializers.TemplateServiceSerializer(
            data=request.data, many=True, context={'request': request, 'template': template})

        if serializer.is_valid():
            try:
                # Use initial_data instead of validated_data in order to be celery friendly
                # and/or make internal API calls with same data
                template.provision(serializer.initial_data, request=request)
            except TemplateProvisionError as e:
                return response.Response(
                    {'detail': "Failed to provision template", 'errors': e.errors},
                    status=status.HTTP_409_CONFLICT)
            else:
                return response.Response(
                    {'detail': 'Provisioning for template services has been scheduled.'},
                    status=status.HTTP_200_OK)
        else:
            return response.Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
