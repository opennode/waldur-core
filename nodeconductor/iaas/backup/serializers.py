from django.core.exceptions import ValidationError
from rest_framework import serializers
from nodeconductor.iaas import models
from nodeconductor.structure import filters as structure_filters
from nodeconductor.structure.serializers import fix_non_nullable_attrs


class InstanceBackupRestorationSerializer(serializers.ModelSerializer):

    cloud_project_membership = serializers.PrimaryKeyRelatedField()
    # TODO: consider unbinding template and persisting its data into backup metadata
    template = serializers.PrimaryKeyRelatedField()
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
            'hostname', 'description',
            #'project',
            'cloud_project_membership',
            'template',
            'flavor',
            'key_name', 'key_fingerprint',
            'system_volume_id', 'system_volume_size',
            'data_volume_id', 'data_volume_size',
        )
        lookup_field = 'uuid'

    def get_fields(self):
        fields = super(InstanceBackupRestorationSerializer, self).get_fields()

        try:
            request = self.context['view'].request
            user = request.user
        except (KeyError, AttributeError):
            return fields

        clouds = structure_filters.filter_queryset_for_user(models.Cloud.objects.all(), user)
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

        try:
            storage_size = models.ResourceQuota.objects.get(cloud_project_membership=membership).storage
        except models.ResourceQuota.DoesNotExist:
            raise serializers.ValidationError(
                "Instance can not be added to cloud account membership, which does not have resource quotas yet.")

        try:
            storage_usage = models.ResourceQuotaUsage.objects.get(cloud_project_membership=membership).storage
        except models.ResourceQuotaUsage.DoesNotExist:
            storage_usage = 0

        system_volume_size = attrs['system_volume_size']
        data_volume_size = attrs.get('data_volume_size', models.Instance.DEFAULT_DATA_VOLUME_SIZE)

        if system_volume_size + data_volume_size > storage_size - storage_usage:
            raise serializers.ValidationError(
                "Requested instance size is over the quota: %s. Available quota: %s" %
                (data_volume_size + system_volume_size, storage_size - storage_usage))

        # TODO: cleanup after migration to drf 3
        return fix_non_nullable_attrs(attrs)

    def restore_object(self, attrs, instance=None):
        flavor = attrs['flavor']
        attrs['cores'] = flavor.cores
        attrs['ram'] = flavor.ram
        attrs['cloud'] = flavor.cloud

        return super(InstanceBackupRestorationSerializer, self).restore_object(attrs, instance)
