from rest_framework import viewsets, status, response

from nodeconductor.jira.client import JiraClient, JiraClientError
from nodeconductor.jira.serializers import IssueSerializer


class IssueViewSet(viewsets.GenericViewSet):
    serializer_class = IssueSerializer

    def get_queryset(self, request):
        return JiraClient().issues.list_by_user(request.user.username)

    def list(self, request):
        issues_list = self.get_queryset(request)
        page = self.paginate_queryset(issues_list)
        if page is not None:
            return self.get_paginated_response(page)
        return response.Response(issues_list)

    def post(self, request):
        issue = self.serializer_class(data=request.data)

        if issue.is_valid():
            try:
                issue.save(owner=request.user)
            except JiraClientError as e:
                return response.Response(
                    {'detail': "Failed to create issue", 'error': str(e)},
                    status=status.HTTP_406_NOT_ACCEPTABLE)
            else:
                return response.Response(
                    {'detail': "Issue has beed created"},
                    status=status.HTTP_409_CONFLICT)

        return response.Response(
            {'detail': "Invalid input data", 'errors': issue.errors},
            status=status.HTTP_400_BAD_REQUEST)
