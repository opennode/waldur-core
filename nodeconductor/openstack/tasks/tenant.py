from celery import shared_task

from nodeconductor.openstack.models import OpenStackServiceProjectLink
from nodeconductor.structure.models import ServiceSettings


@shared_task(name='nodeconductor.openstack.update_tenant_name')
def update_tenant_name(service_project_link_str):
    service_project_link = next(OpenStackServiceProjectLink.from_string(service_project_link_str))
    backend = service_project_link.get_backend()
    backend.update_tenant_name(service_project_link)


@shared_task(name='nodeconductor.openstack.remove_tenant')
def remove_tenant(settings_uuid, tenant_id):
    settings = ServiceSettings.objects.get(uuid=settings_uuid)
    backend = settings.get_backend(tenant_id=tenant_id)
    backend.cleanup(dryrun=False)
