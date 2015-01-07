from __future__ import unicode_literals

from nodeconductor.core import models as core_models
from nodeconductor.core.serializers import UnboundSerializerMethodField
from nodeconductor.structure.filters import filter_queryset_for_user


def get_related_clouds(obj, request):
    related_clouds = obj.clouds.all()

    try:
        user = request.user
        related_clouds = filter_queryset_for_user(related_clouds, user)
    except AttributeError:
        pass

    from nodeconductor.iaas.serializers import BasicCloudSerializer

    serializer_instance = BasicCloudSerializer(related_clouds, many=True, context={'request': request})

    return serializer_instance.data


def add_clouds_to_related_model(sender, fields, **kwargs):
    fields['clouds'] = UnboundSerializerMethodField(get_related_clouds)


def propagate_new_users_key_to_his_projects_clouds(sender, instance=None, created=False, **kwargs):
    if not created:
        return

    public_key = instance

    from nodeconductor.iaas.models import CloudProjectMembership

    membership_queryset = filter_queryset_for_user(
        CloudProjectMembership.objects.all(), public_key.user)

    membership_pks = membership_queryset.values_list('pk', flat=True)

    if membership_pks:
        # Note: importing here to avoid circular import hell
        from nodeconductor.iaas import tasks

        tasks.push_ssh_public_keys.delay([public_key.uuid.hex], list(membership_pks))


def propagate_users_keys_to_clouds_of_newly_granted_project(sender, structure, user, role, **kwargs):
    project = structure

    ssh_public_key_uuids = core_models.SshPublicKey.objects.filter(
        user=user).values_list('uuid', flat=True)

    from nodeconductor.iaas.models import CloudProjectMembership

    membership_pks = CloudProjectMembership.objects.filter(
        project=project).values_list('pk', flat=True)

    if ssh_public_key_uuids and membership_pks:
        # Note: importing here to avoid circular import hell
        from nodeconductor.iaas import tasks

        tasks.push_ssh_public_keys.delay(
            list(ssh_public_key_uuids), list(membership_pks))


def create_initial_security_groups(sender, instance=None, created=False, **kwargs):
    if not created:
        return

    from nodeconductor.iaas.models import SecurityGroup

    # TODO: Get from settings
    # group http
    http_group = SecurityGroup.objects.create(
        name='http',
        description='Security group for web servers',
        cloud_project_membership=instance,
    )
    http_group.rules.create(
        protocol='tcp',
        from_port=80,
        to_port=80,
        cidr='0.0.0.0/0',
    )

    # group https
    https_group = SecurityGroup.objects.create(
        name='https',
        description='Security group for web servers with https traffic',
        cloud_project_membership=instance,
    )
    https_group.rules.create(
        protocol='tcp',
        from_port=443,
        to_port=443,
        cidr='0.0.0.0/0',
    )
