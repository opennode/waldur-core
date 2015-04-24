from rest_framework import viewsets, mixins, status, response, exceptions

from nodeconductor.jira.client import JiraClient, JiraClientError
from nodeconductor.jira.serializers import IssueSerializer, CommentSerializer


class IssueViewSet(mixins.RetrieveModelMixin, mixins.ListModelMixin,
                   mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = IssueSerializer

    def get_queryset(self):
        return JiraClient().issues.list_by_user(self.request.user.username)

    def get_object(self):
        try:
            return JiraClient().issues.get_by_user(
                self.request.user.username, self.kwargs['pk'])
        except JiraClientError as e:
            raise exceptions.NotFound(e)

    def perform_create(self, serializer):
        try:
            serializer.save(reporter=self.request.user.username)
        except JiraClientError as e:
            return response.Response(
                {'detail': "Failed to create issue", 'error': str(e)},
                status=status.HTTP_409_CONFLICT)


class CommentViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = CommentSerializer

    def get_queryset(self):
        return JiraClient().comments.list(self.kwargs['pk'])

    def perform_create(self, serializer):
        try:
            serializer.save(issue=self.kwargs['pk'])
        except JiraClientError as e:
            return response.Response(
                {'detail': "Failed to create comment", 'error': str(e)},
                status=status.HTTP_409_CONFLICT)
