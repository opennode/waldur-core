import logging

from celery import shared_task

from nodeconductor.openstack.models import Instance


logger = logging.getLogger(__name__)


@shared_task(name='nodeconductor.openstack.sync_instance_security_groups')
def sync_instance_security_groups(instance_uuid):
    instance = Instance.objects.get(uuid=instance_uuid)
    backend = instance.get_backend()
    backend.sync_instance_security_groups(instance)
