from rest_framework import serializers

from nodeconductor.jira.client import JiraClient


class TicketSerializer(serializers.Serializer):
    summary = serializers.CharField()
    description = serializers.CharField(style={'base_template': 'textarea.html'}, required=False)

    def save(self, owner):
        self.owner = owner
        return super(TicketSerializer, self).save()

    def create(self, validated_data):
        return JiraClient().tickets.create(
            validated_data['summary'], validated_data['description'], reporter=self.owner.username)
