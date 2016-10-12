
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from nodeconductor.users import models


@shared_task(name='nodeconductor.users.cancel_expired_invitations')
def cancel_expired_invitations(invitations=None):
    """
    Invitation lifetime must be specified in NodeConductor settings with parameter
    "INVITATION_LIFETIME". If invitation creation time is less than expiration time, it will be canceled.
    """
    expiration_date = timezone.now() - settings.NODECONDUCTOR['INVITATION_LIFETIME']
    if not invitations:
        invitations = models.Invitation.objects.filter(state=models.Invitation.State.PENDING)
    invitations = invitations.filter(created__lte=expiration_date)
    invitations.update(state=models.Invitation.State.CANCELED)
