from simplejson import JSONDecodeError

from rest_framework import viewsets, decorators, exceptions, status
from rest_framework.response import Response

from nodeconductor.core import filters as core_filters
from nodeconductor.structure import filters as structure_filters
from nodeconductor.template import models, serializers, filters


class TemplateGroupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.TemplateGroup.objects.filter(is_active=True).prefetch_related('templates')
    serializer_class = serializers.TemplateGroupSerializer
    lookup_field = 'uuid'
    filter_class = filters.TemplateGroupFilter
    filter_backends = (core_filters.DjangoMappingFilterBackend, structure_filters.TagsFilter)
    # Parameters for TagsFilter that support complex filtering by templates tags.
    tags_filter_db_field = 'templates__tags'
    tags_filter_request_field = 'templates_tag'

    def list(self, request, *args, **kwargs):
        """
        To get a list of all template groups, issue **GET** request against */api/templates-groups/*.

        Supported filters are:

         - tag=<template group tag>, can be list. If template group has at least one of tags - it will be returned.
         - rtag=<template group tag>, can be list. If template group has all rtags - it will be returned.
         - name=<template group name>.
         - templates_tag=<template tag>, filter templates groups that contain template with given tag. Can be list.
         - templates_rtag=<template tag>, the same as rtag but for templates. Can be list.
         - templates_tag__license-os=centos7 - filter by template tag with particular prefix.
                                              (deprecated, use templates_rtag instead).
         - project=<project_url> filter all template groups that could be provisioned with given project.
         - project_uuid=<project_uuid> filter all template groups that could be provisioned with given project.

         Template field "order_number" shows templates execution order:
         template with lowest order number will be executed first.
        """
        return super(TemplateGroupViewSet, self).list(request, *args, **kwargs)

    @decorators.detail_route(methods=['post'])
    def provision(self, request, uuid=None):
        """
        Schedule head(first) template provision synchronously, tail templates - as task.

        To start a template group provisioning, issue **POST** request against */api/templates-groups/<uuid>/provision/*
        with a list of templates' additional options. Additional options should contain options
        for what should be added to template options and passed to resource provisioning endpoint.

        Additional options example:

        .. code-block:: javascript

            [
                // options for first template
                {
                    "name": "test-openstack-instance",
                    "system_volume_size": 20
                },
                // options for second template
                {
                    "host_group": "zabbix-host-group"
                }
            ]

        Method will return validation errors if they occurs on head template provision.
        If head template provision succeed - method will return URL of template group result.
        """
        group = self.get_object()
        templates_additional_options = self._get_templates_additional_options(request)
        # execute request to head(first) template and raise exception if its validation fails
        try:
            response = group.schedule_head_template_provision(request, templates_additional_options)
        except models.TemplateActionException as e:
            return Response({'error_message': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        if not response.ok:
            try:
                return Response(response.json(), status=response.status_code)
            except JSONDecodeError:
                return Response(
                    {'Error message': 'cannot schedule head template provision %s' % response.content},
                    status=response.status_code)
        # schedule tasks for other templates provision
        result = group.schedule_tail_templates_provision(request, templates_additional_options, response)
        serialized_result = serializers.TemplateGroupResultSerializer(result, context={'request': request}).data
        return Response(serialized_result, status=status.HTTP_200_OK)

    def _get_templates_additional_options(self, request):
        """ Get additional options from request, validate them and transform to internal values """
        group = self.get_object()
        inputed_additional_options = request.data or []
        if not isinstance(inputed_additional_options, list):
            raise exceptions.ParseError(
                'Cannot parse templates additional options. '
                'Required format: [{template1_option1: value1, template1_option2: value2 ...}, {template2_option: ...}]')

        templates = group.templates.order_by('order_number')
        if len(inputed_additional_options) > templates.count():
            raise exceptions.ParseError(
                'Too many additional options provided, group has only %s templates.' % templates.count())

        for options in inputed_additional_options:
            if not isinstance(options, dict):
                raise exceptions.ParseError(
                    'Cannot parse templates options %s - they should be dictionary' % options)

        templates_additional_options = dict(zip(templates, inputed_additional_options))
        return templates_additional_options


class TemplateGroupResultViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.TemplateGroupResult.objects.all()
    serializer_class = serializers.TemplateGroupResultSerializer
    lookup_field = 'uuid'

    def list(self, request, *args, **kwargs):
        """
        To get a list of template group results - issue **POST** request against */api/templates-results/*.

        Template group result has the following fields:

         - url
         - uuid
         - is_finished - false if corresponding template group is provisioning resources, true otherwise
         - is_erred - true if corresponding template group provisioning has failed
         - provisioned_resources - list of resources URLs that were provisioned by the template group
         - state_message - human-readable description of the state of the provisioning group
         - error_message - human-readable error message (empty if provisioning was successful)
         - error_details - technical details of the error
        """
        return super(TemplateGroupResultViewSet, self).list(request, *args, **kwargs)
