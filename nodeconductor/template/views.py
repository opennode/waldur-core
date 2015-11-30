from simplejson import JSONDecodeError

from rest_framework import viewsets, decorators, exceptions, status, reverse
from rest_framework.response import Response

from nodeconductor.core import filters as core_filters
from nodeconductor.template import models, serializers, filters


class TemplateGroupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.TemplateGroup.objects.filter(is_active=True).prefetch_related('templates')
    serializer_class = serializers.TemplateGroupSerializer
    lookup_field = 'uuid'
    filter_class = filters.TemplateGroupFilter
    filter_backends = (core_filters.DjangoMappingFilterBackend,)

    @decorators.detail_route(methods=['post'])
    def provision(self, request, uuid=None):
        """ Schedule head(first) template provision synchronously, tail templates - as task.

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
                    {'Error message': 'cannot schedule head template provision'}, status=response.status_code)
        # schedule tasks for other templates provision
        result = group.schedule_tail_templates_provision(request, templates_additional_options, response)
        result_url = reverse.reverse('template-result-detail', args=(result.uuid.hex, ), request=request)
        return Response({'result_url': result_url}, status=status.HTTP_200_OK)

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
