from rest_framework import generics, response

from nodeconductor.events import elasticsearch_client


class EventListView(generics.GenericAPIView):

    def list(self, request, *args, **kwargs):
        order_by = request.GET.get('o', '-@timestamp')
        event_types = request.GET.getlist('event_type')
        search_text = request.GET.get('search_text')
        elasticsearch_list = elasticsearch_client.ElasticsearchResultList(
            user=request.user, sort=order_by, event_types=event_types, search_text=search_text)

        page = self.paginate_queryset(elasticsearch_list)
        if page is not None:
            return self.get_paginated_response(page)
        return response.Response(elasticsearch_list)

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)
