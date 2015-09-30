from django.core.exceptions import ValidationError
from rest_framework import serializers
from nodeconductor.iaas import models
from nodeconductor.structure.managers import filter_queryset_for_user


class InstanceBackupRestorationSerializer(serializers.ModelSerializer):

    cloud_project_membership = serializers.PrimaryKeyRelatedField(queryset=models.CloudProjectMembership.objects.all())
    # TODO: consider unbinding template and persisting its data into backup metadata
    template = serializers.PrimaryKeyRelatedField(queryset=models.Template.objects.all())
    flavor = serializers.HyperlinkedRelatedField(
        view_name='flavor-detail',
        lookup_field='uuid',
        queryset=models.Flavor.objects.all(),
        required=True,
        write_only=True,
    )

    system_volume_id = serializers.CharField(required=False)
    system_volume_size = serializers.IntegerField(required=False, min_value=0)
    data_volume_id = serializers.CharField(required=False)
    data_volume_size = serializers.IntegerField(required=False, min_value=0)

    class Meta(object):
        model = models.Instance
        fields = (
            'name', 'description',
            'cloud_project_membership',
            'template',
            'flavor',
            'key_name', 'key_fingerprint',
            'system_volume_id', 'system_volume_size',
            'data_volume_id', 'data_volume_size',
            'agreed_sla',
            'type', 'user_data',
        )
        extra_kwargs = {
            'url': {'lookup_field': 'uuid'},
        }

    def get_fields(self):
        fields = super(InstanceBackupRestorationSerializer, self).get_fields()

        try:
            request = self.context['view'].request
            user = request.user
        except (KeyError, AttributeError):
            return fields

        clouds = filter_queryset_for_user(models.Cloud.objects.all(), user)
        fields['template'].queryset = fields['template'].queryset.filter(images__cloud__in=clouds).distinct()

        return fields

    def validate(self, attrs):
        flavor = attrs['flavor']
        project = attrs['cloud_project_membership'].project
        try:
            membership = models.CloudProjectMembership.objects.get(
                project=project,
                cloud=flavor.cloud,
            )
        except models.CloudProjectMembership.DoesNotExist:
            raise ValidationError("Flavor is not within project's clouds.")

        template = attrs['template']
        image_exists = models.Image.objects.filter(template=template, cloud=flavor.cloud).exists()

        if not image_exists:
            raise serializers.ValidationError("Template %s is not available on cloud %s"
                                              % (template, flavor.cloud))

        system_volume_size = attrs['system_volume_size']
        data_volume_size = attrs.get('data_volume_size', models.Instance.DEFAULT_DATA_VOLUME_SIZE)
        quota_usage = {
            'storage': system_volume_size + data_volume_size,
            'vcpu': flavor.cores,
            'ram': flavor.ram,
        }

        quota_errors = membership.validate_quota_change(quota_usage)
        if quota_errors:
            raise serializers.ValidationError(
                'One or more quotas are over limit: \n' + '\n'.join(quota_errors))

        return attrs

    def create(self, validated_data):
        flavor = validated_data.pop('flavor')
        validated_data['cores'] = flavor.cores
        validated_data['ram'] = flavor.ram

        return super(InstanceBackupRestorationSerializer, self).create(validated_data)
