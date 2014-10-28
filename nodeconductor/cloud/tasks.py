from celery import shared_task


@shared_task
def create_backend_membership(membership):
    """
    Execute membership create_in_backend method as celery task
    """
    membership.create_in_backend()
