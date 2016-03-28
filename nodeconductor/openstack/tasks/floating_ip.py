import logging

from celery import shared_task

from nodeconductor.openstack.backend import OpenStackBackendError
from nodeconductor.openstack.models import Instance

logger = logging.getLogger(__name__)


# XXX: This task should be replaced with executor
@shared_task(name='nodeconductor.openstack.assign_floating_ip')
def assign_floating_ip(instance_uuid, floating_ip_uuid):
    instance = Instance.objects.get(uuid=instance_uuid)
    floating_ip = instance.service_project_link.floating_ips.get(uuid=floating_ip_uuid)
    backend = instance.cloud.get_backend()

    try:
        backend.assign_floating_ip_to_instance(instance, floating_ip)
    except OpenStackBackendError:
        logger.warning("Failed to assign floating IP to the instance with id %s.", instance_uuid)
