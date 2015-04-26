from rest_framework import generics, response, settings

from nodeconductor.events import elasticsearch_client


class EventListView(generics.GenericAPIView):

    def list(self, request, *args, **kwargs):
        order_by = request.query_params.get('o', '-@timestamp')
        event_types = request.query_params.getlist('event_type')
        search_param = settings.api_settings.SEARCH_PARAM
        search_text = request.query_params.get(search_param)
        elasticsearch_list = elasticsearch_client.ElasticsearchResultList(
            user=request.user, sort=order_by, event_types=event_types, search_text=search_text)

        page = self.paginate_queryset(elasticsearch_list)
        if page is not None:
            return self.get_paginated_response(page)
        return response.Response(elasticsearch_list)

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)
