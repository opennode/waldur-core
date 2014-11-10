from __future__ import unicode_literals

import logging

from celery import shared_task
from django.contrib.auth import get_user_model

from nodeconductor.cloud import models
from nodeconductor.cloud.backend import CloudBackendError
from nodeconductor.core import models as core_models
from nodeconductor.core.tasks import tracked_processing
from nodeconductor.structure import models as structure_models
from nodeconductor.structure.filters import filter_queryset_for_user


logger = logging.getLogger(__name__)


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
    for public_key in core_models.SshPublicKey.objects.filter(
            user__groups__projectrole__project=membership.project).iterator():
        try:
            backend.push_ssh_public_key(membership, public_key)
        except CloudBackendError:
            logger.warn(
                'Failed to push public key %s to cloud membership %s',
                public_key.uuid, membership.pk,
                exc_info=1,
            )


@shared_task
def push_ssh_public_keys(ssh_public_keys_uuids, membership_pks):
    public_keys = models.SshPublicKey.objects.filter(uuid__in=ssh_public_keys_uuids)

    existing_keys = set(k.uuid.hex for k in public_keys)
    missing_keys = set(ssh_public_keys_uuids) - existing_keys
    if missing_keys:
        logging.warn(
            'Failed to push missing public keys: %s',
            ', '.join(missing_keys)
        )

    membership_queryset = models.CloudProjectMembership.objects.filter(
        pk__in=membership_pks)

    for membership in membership_queryset.iterator():
        if membership.state != core_models.SynchronizationStates.IN_SYNC:
            logging.warn(
                'Not pushing public keys to cloud membership %s which is in state %s',
                membership.pk, membership.get_state_display()
            )
            continue

        backend = membership.cloud.get_backend()
        for public_key in public_keys:
            try:
                backend.push_ssh_public_key(membership, public_key)
            except CloudBackendError:
                logger.warn(
                    'Failed to push public key %s to cloud membership %s',
                    public_key.uuid, membership.pk,
                    exc_info=1,
                )
