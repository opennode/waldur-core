from celery import shared_task
from keystoneclient.v2_0 import client

from nodeconductor.cloud import models

# XXX: this have to be moved to settings or implemented in other way
ADMIN_TENANT = 'admin'


@shared_task
def connect_project_to_cloud(cloud, project):
    """
    Connect project to cloud, add new tenant and store its uuid in membership model
    """
    keystone = client.Client(cloud.username, cloud.password, ADMIN_TENANT, auth_url=cloud.auth_url)
    tenant = keystone.tenants.create(tenant_name=project.name, description=project.description, enabled=True)
    models.CloudProjectMembership.objects.create(
        cloud=cloud, project=project, tenant_uuid=tenant.id)
