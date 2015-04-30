
from rest_framework import serializers, exceptions

from nodeconductor.core.models import SshPublicKey
from nodeconductor.iaas.models import Cloud, Flavor, Image, CloudProjectMembership, IaasTemplateService
from nodeconductor.iaas.serializers import FlavorSerializer
from nodeconductor.structure.models import Project


class CloudSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Cloud
        fields = ('url', 'uuid', 'auth_url', 'name')
        lookup_field = 'uuid'


class ProjectSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Project
        fields = ('url', 'uuid', 'name', 'description')
        lookup_field = 'uuid'


class ImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Image
        fields = ('backend_id',)


class IaasTemplateServiceSerializer(serializers.ModelSerializer):
    service = CloudSerializer(read_only=True)
    project = ProjectSerializer(read_only=True)
    flavor = FlavorSerializer(read_only=True)
    image = ImageSerializer(read_only=True)

    class Meta:
        model = IaasTemplateService
        fields = (
            'name', 'service', 'project', 'flavor', 'image', 'sla', 'sla_level', 'backup_schedule'
        )


class IaasTemplateServiceCreateSerializer(serializers.Serializer):
    name = serializers.CharField()
    service = serializers.HyperlinkedRelatedField(
        view_name='cloud-detail',
        lookup_field='uuid',
        queryset=Cloud.objects.all(),
    )
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
    image = serializers.CharField()
    sla = serializers.BooleanField(required=False)
    sla_level = serializers.DecimalField(max_digits=6, decimal_places=4, required=False)
    backup_schedule = serializers.CharField(required=False)

    # Extra fields, not predefined within template
    description = serializers.CharField(required=False)
    system_volume_size = serializers.IntegerField(required=False)
    data_volume_size = serializers.IntegerField(required=False)
    ssh_public_key = serializers.HyperlinkedRelatedField(
        view_name='sshpublickey-detail',
        lookup_field='uuid',
        queryset=SshPublicKey.objects.all(),
        required=False,
        write_only=True,
    )

    def run_validation(self, data=()):
        validated_data = super(IaasTemplateServiceCreateSerializer, self).run_validation(data)

        try:
            cpm = CloudProjectMembership.objects.get(
                cloud=validated_data['service'],
                project=validated_data['project'])
            image = Image.objects.filter(cloud=cpm.cloud).filter(backend_id=data.get('image')).first()
        except CloudProjectMembership.DoesNotExist:
            raise exceptions.ValidationError(
                {'project': "CloudProjectMembership with project=%s "
                 "and cloud=%s does not exist." % (data.get('project'), data.get('service'))})
        except Image.DoesNotExist:
            raise exceptions.ValidationError(
                {'image': "Image with backend_id=%s does not exist." % data.get('image')})
        else:
            validated_data['image'] = image

        return validated_data
