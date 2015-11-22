from __future__ import unicode_literals

from rest_framework import viewsets, decorators, response, status, exceptions

from nodeconductor.template import models, serializers, get_template_services, TemplateProvisionError


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
                    "flavor": "http://example.com/api/flavors/d760e6a00b5949bdb87e5f0dcfacd804/",
                    "template": "http://example.com/api/iaas-templates/fffb21de7bfd47de9661e9d9fdd4d619/",
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
            Additional options required for provisioning could be passed and will be
            forwarded to specific service provisioning with no change.
        """
        template = self.get_object()
        services = {service.service_type: service for service in get_template_services()}
        initdata = request.data or []

        def fill_data_from_req_or_db(data, service_cls):
            cur_service = service_cls.objects.get(base_template=template)
            cur_serializer = service_cls._serializer(cur_service, context={'request': request})

            for field in cur_serializer.fields:
                if hasattr(cur_service, field) and field not in data:
                    value = cur_serializer.data[field]
                    if value is not None:
                        data[field] = value

            return data

        if not isinstance(initdata, list):
            raise exceptions.ParseError("Invalid input data, JSON list expected.")

        # Inspect services from POST request and fill missed fields from DB if required
        for data in initdata:
            service_type = data.get('service_type')
            if service_type not in services.keys():
                raise exceptions.ParseError(
                    "Unsupported service type %s" % data.get('service_type'))
            else:
                fill_data_from_req_or_db(data, services[service_type])
                del services[service_type]

        # Use data from DB for missed services in POST
        for service_type, service in services.items():
            initdata.append(fill_data_from_req_or_db({'service_type': service_type}, service))

        serializer = serializers.TemplateServiceSerializer(
            data=initdata, many=True, context={'request': request, 'template': template})

        if serializer.is_valid():
            try:
                template.provision(initdata, request=request)
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
