from celery import shared_task

from nodeconductor.openstack.models import OpenStackServiceProjectLink


@shared_task(name='nodeconductor.openstack.update_tenant_name')
def update_tenant_name(service_project_link_str):
    service_project_link = next(OpenStackServiceProjectLink.from_string(service_project_link_str))
    backend = service_project_link.get_backend()
    backend.update_tenant_name(service_project_link)
