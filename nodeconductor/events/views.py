from __future__ import unicode_literals

from rest_framework import generics, response, settings

from nodeconductor.events import elasticsearch_client


class EventListView(generics.GenericAPIView):

    ADDITIONAL_SEARCH_FIELDS = ['user_uuid', 'customer_uuid', 'project_uuid', 'project_group_uuid']

    def get_queryset(self, request):
        return elasticsearch_client.ElasticsearchResultList(request.user)

    def filter(self, request):
        search_text = request.query_params.get(settings.api_settings.SEARCH_PARAM)
        event_types = request.query_params.getlist('event_type')
        search_kwargs = {field: request.query_params.get(field)
                         for field in self.ADDITIONAL_SEARCH_FIELDS if field in request.query_params}
        self.queryset = self.queryset.filter(
            event_types=event_types,
            search_text=search_text,
            **search_kwargs)

    def order(self, request):
        order_by = request.query_params.get('o', '-@timestamp')
        self.queryset = self.queryset.order_by(order_by)

    def list(self, request, *args, **kwargs):
        self.queryset = self.get_queryset(request)
        self.filter(request)
        self.order(request)

        page = self.paginate_queryset(self.queryset)
        if page is not None:
            return self.get_paginated_response(page)
        return response.Response(self.queryset)

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)
