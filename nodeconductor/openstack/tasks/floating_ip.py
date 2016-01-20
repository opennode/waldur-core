import logging

from celery import shared_task

from nodeconductor.openstack.backend import OpenStackBackendError
from nodeconductor.openstack.models import Instance, OpenStackServiceProjectLink

logger = logging.getLogger(__name__)


@shared_task(name='nodeconductor.openstack.allocate_floating_ip')
def allocate_floating_ip(service_project_link_str):
    service_project_link = next(OpenStackServiceProjectLink.from_string(service_project_link_str))
    backend = service_project_link.get_backend()

    try:
        backend.allocate_floating_ip_address(service_project_link)
    except OpenStackBackendError:
        logger.warning(
            "Failed to allocate floating IP for service project link %s.",
            service_project_link_str)


@shared_task(name='nodeconductor.openstack.assign_floating_ip')
def assign_floating_ip(instance_uuid, floating_ip_uuid):
    instance = Instance.objects.get(uuid=instance_uuid)
    floating_ip = instance.service_project_link.floating_ips.get(uuid=floating_ip_uuid)
    backend = instance.cloud.get_backend()

    try:
        backend.assign_floating_ip_to_instance(instance, floating_ip)
    except OpenStackBackendError:
        logger.warning("Failed to assign floating IP to the instance with id %s.", instance_uuid)
