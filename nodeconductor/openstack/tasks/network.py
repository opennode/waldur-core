import logging

from celery import shared_task

from nodeconductor.openstack.backend import OpenStackBackendError
from nodeconductor.openstack.models import OpenStackServiceProjectLink

logger = logging.getLogger(__name__)


@shared_task(name='nodeconductor.openstack.sync_external_network')
def sync_external_network(service_project_link_str, action, data=None):
    service_project_link = next(OpenStackServiceProjectLink.from_string(service_project_link_str))
    backend = service_project_link.get_backend()

    if not data:
        data = {}

    try:
        func = getattr(backend, '%s_external_network' % action)
        func(service_project_link, **data)
    except OpenStackBackendError:
        logger.warning(
            "Failed to %s external network for service project link %s.",
            action, service_project_link_str)
