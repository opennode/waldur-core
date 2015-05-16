
from rest_framework import serializers

from nodeconductor.iaas.models import Flavor, Template, IaasTemplateService
from nodeconductor.structure.models import Project


class IaasTemplateServiceSerializer(serializers.ModelSerializer):
    project = serializers.HyperlinkedRelatedField(
        view_name='project-detail',
        lookup_field='uuid',
        queryset=Project.objects.all(),
    )
    flavor = serializers.HyperlinkedRelatedField(
        view_name='flavor-detail',
        lookup_field='uuid',
        queryset=Flavor.objects.all(),
    )
    template = serializers.HyperlinkedRelatedField(
        view_name='iaastemplate-detail',
        lookup_field='uuid',
        queryset=Template.objects.all(),
    )

    class Meta:
        model = IaasTemplateService
        fields = (
            'name', 'project', 'flavor', 'template', 'backup_schedule'
        )
