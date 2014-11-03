from celery import shared_task

from nodeconductor.cloud import models
from nodeconductor.core import models as core_models
from nodeconductor.core.tasks import tracked_processing


@shared_task
@tracked_processing(
    models.Cloud,
    processing_state='begin_pushing',
    desired_state='set_in_sync',
)
def push_cloud_account(cloud_uuid):
    cloud = models.Cloud.objects.get(uuid=cloud_uuid)
    cloud.get_backend().push_cloud_account(cloud)


@shared_task
@tracked_processing(
    models.CloudProjectMembership,
    processing_state='begin_pushing',
    desired_state='set_in_sync',
)
def push_cloud_membership(membership_pk):
    membership = models.CloudProjectMembership.objects.get(pk=membership_pk)
    membership.cloud.get_backend().push_membership(membership)


@shared_task
@tracked_processing(
    models.CloudProjectMembership,
    processing_state='begin_pushing',
    desired_state='set_in_sync',
)
def initial_push_cloud_membership(membership_pk):
    membership = models.CloudProjectMembership.objects.get(pk=membership_pk)

    backend = membership.cloud.get_backend()

    # Propagate cloud-project membership itself
    backend.push_membership(membership)

    # Propagate ssh public keys of users involved in the project
    for ssh_key in core_models.SshPublicKey.objects.filter(
            user__groups__projectrole__project=membership.project).iterator():
        backend.push_ssh_public_key(membership, ssh_key)
