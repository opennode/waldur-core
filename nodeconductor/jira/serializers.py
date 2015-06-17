import re

from rest_framework import serializers

from nodeconductor.jira.backend import JiraClient


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
            validated_data.get('summary'),
            validated_data.get('description'),
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

    AUTHOR_RE = re.compile("Comment posted by user ([\w.@+-]+) \(([0-9a-z]{32})\)")
    AUTHOR_TEMPLATE = "Comment posted by user {username} ({uuid})\n{body}"

    def save(self, issue):
        self.issue = issue
        return super(CommentSerializer, self).save()

    def create(self, validated_data):
        return JiraClient().comments.create(self.issue, self.serialize_body())

    def to_representation(self, obj):
        """
        Try to extract injected author information.
        Use original author otherwise.
        """
        data = super(CommentSerializer, self).to_representation(obj)
        author, body = self.parse_body(data['body'])
        data['author'] = author or data['author']
        data['body'] = body
        return data

    def serialize_body(self):
        """
        Inject author's name and UUID into comment's body
        """
        body = self.validated_data['body']
        user = self.context['request'].user
        return self.AUTHOR_TEMPLATE.format(username=user.username, uuid=user.uuid.hex, body=body)

    def parse_body(self, body):
        """
        Extract author's name and UUID from comment's body
        """
        match = re.match(self.AUTHOR_RE, body)
        if match:
            username = match.group(1)
            uuid = match.group(2)
            body = body[match.end(2) + 2:]
            author = {'displayName': username, 'uuid': uuid}
            return author, body
        else:
            return None, body
