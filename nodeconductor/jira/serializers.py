from rest_framework import serializers

from nodeconductor.jira.client import JiraClient


class UserSerializer(serializers.Serializer):
    displayName = serializers.CharField()
    emailAddress = serializers.EmailField()


class IssueSerializer(serializers.Serializer):
    url = serializers.HyperlinkedIdentityField(view_name='issue-detail')
    key = serializers.ReadOnlyField()
    summary = serializers.CharField()
    description = serializers.CharField(required=False, style={'base_template': 'textarea.html'})
    assignee = UserSerializer(read_only=True)
    created = serializers.DateTimeField(read_only=True)
    comments = serializers.HyperlinkedIdentityField(view_name='issue-comments-list')

    def save(self, reporter):
        self.reporter = reporter
        return super(IssueSerializer, self).save()

    def create(self, validated_data):
        return JiraClient().issues.create(
            validated_data['summary'],
            validated_data['description'],
            reporter=self.reporter)

    def to_representation(self, obj):
        obj.pk = obj.key
        for field in self.fields:
            if hasattr(obj.fields, field):
                setattr(obj, field, getattr(obj.fields, field))

        return super(IssueSerializer, self).to_representation(obj)


class CommentSerializer(serializers.Serializer):
    author = UserSerializer(read_only=True)
    created = serializers.DateTimeField(read_only=True)
    body = serializers.CharField()

    def save(self, issue):
        self.issue = issue
        return super(CommentSerializer, self).save()

    def create(self, validated_data):
        return JiraClient().comments.create(self.issue, validated_data['body'])
