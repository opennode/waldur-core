from rest_framework import viewsets, status, response

from nodeconductor.jira.client import JiraClient, JiraClientError
from nodeconductor.jira.serializers import TicketSerializer


class TicketViewSet(viewsets.GenericViewSet):
    serializer_class = TicketSerializer

    def get_queryset(self, request):
        return JiraClient().tickets.list_by_user(request.user.username)

    def list(self, request):
        tickets_list = self.get_queryset(request)
        page = self.paginate_queryset(tickets_list)
        if page is not None:
            return self.get_paginated_response(page)
        return response.Response(tickets_list)

    def post(self, request):
        ticket = self.serializer_class(data=request.data)

        if ticket.is_valid():
            try:
                ticket.save(owner=request.user)
            except JiraClientError as e:
                return response.Response(
                    {'detail': "Failed to create ticket", 'error': str(e)},
                    status=status.HTTP_406_NOT_ACCEPTABLE)
            else:
                return response.Response(
                    {'detail': "Ticked has beed created"},
                    status=status.HTTP_200_OK)

        return response.Response(
            {'detail': "Invalid input data", 'errors': ticket.errors},
            status=status.HTTP_400_BAD_REQUEST)
