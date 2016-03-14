import logging

from celery import shared_task

from nodeconductor.openstack.backend import OpenStackBackendError
from nodeconductor.openstack.models import Instance, OpenStackServiceProjectLink


logger = logging.getLogger(__name__)


@shared_task(name='nodeconductor.openstack.sync_instance_security_groups')
def sync_instance_security_groups(instance_uuid):
    instance = Instance.objects.get(uuid=instance_uuid)
    backend = instance.get_backend()
    backend.sync_instance_security_groups(instance)


@shared_task(name='nodeconductor.openstack.openstack_pull_security_groups')
def openstack_pull_security_groups(service_project_link_str):
    service_project_link = next(OpenStackServiceProjectLink.from_string(service_project_link_str))
    backend = service_project_link.get_backend()

    try:
        backend.pull_security_groups(service_project_link)
    except OpenStackBackendError:
        logger.warning("Failed to pull security groups for service project link %s.",
                       service_project_link_str)


@shared_task(name='nodeconductor.openstack.openstack_push_security_groups')
def openstack_push_security_groups(service_project_link_str):
    service_project_link = next(OpenStackServiceProjectLink.from_string(service_project_link_str))
    backend = service_project_link.get_backend()

    try:
        backend.push_security_groups(service_project_link)
    except OpenStackBackendError:
        logger.warning("Failed to push security groups for service project link %s.",
                       service_project_link_str)
