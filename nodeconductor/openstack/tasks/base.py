from celery import shared_task, current_app
from functools import wraps

from nodeconductor.openstack import models
from nodeconductor.openstack.backend import OpenStackClient
from nodeconductor.core.tasks import retry_if_false, BackendMethodTask
from nodeconductor.core.utils import deserialize_instance


def track_openstack_session(task_fn):
    @wraps(task_fn)
    def wrapped(tracked_session, *args, **kwargs):
        client = OpenStackClient(session=tracked_session)
        task_fn(client, *args, **kwargs)
        return client.session
    return wrapped


def save_error_message_from_task(func):
    @wraps(func)
    def wrapped(task_uuid, *args, **kwargs):
        func(*args, **kwargs)
        result = current_app.AsyncResult(task_uuid)
        transition_entity = kwargs['transition_entity']
        message = result.result['exc_message']
        if message:
            transition_entity.error_message = message
            transition_entity.save(update_fields=['error_message'])
    return wrapped


@shared_task
@track_openstack_session
def nova_server_resize(client, server_id, flavor_id):
    client.nova.servers.resize(server_id, flavor_id, 'MANUAL')


@shared_task
@track_openstack_session
def nova_server_resize_confirm(client, server_id):
    client.nova.servers.confirm_resize(server_id)


@shared_task(max_retries=300, default_retry_delay=3)
@track_openstack_session
@retry_if_false
def nova_wait_for_server_status(client, server_id, status):
    server = client.nova.servers.get(server_id)
    return server.status == status


@shared_task
def delete_tenant_with_spl(serialized_tenant):
    tenant = deserialize_instance(serialized_tenant)
    spl = tenant.service_project_link
    tenant.delete()
    spl.delete()


# Temporary task. Should be removed after tenant will be connected to instance.
class SecurityGroupCreationTask(BackendMethodTask):
    """ Create tenant for SPL if it does not exist and execute backend method """

    def create_tenant(self, spl, security_group):
        """ Create tenant for SPL via executor.

        Creation ignores security groups pull to avoid new group deletion.
        """
        from nodeconductor.openstack import executors

        tenant = spl.create_tenant()
        executors.TenantCreateExecutor.execute(tenant, async=False, pull_security_groups=False)
        tenant.refresh_from_db()
        if tenant.state != models.Tenant.States.OK:
            security_group.set_erred()
            security_group.error_message = 'Tenant %s (PK: %s) creation failed.' % (tenant, tenant.pk)
            security_group.save()
        return tenant

    def execute(self, security_group, *args, **kwargs):
        spl = security_group.service_project_link
        if spl.tenant is None:
            from nodeconductor.openstack import executors
            # Create tenant without security groups
            tenant = self.create_tenant(spl, security_group)
            # Create new security group
            backend = tenant.get_backend()
            backend.create_security_group(security_group, *args, **kwargs)
            # Pull all security groups
            executors.TenantPullSecurityGroupsExecutor.execute(tenant, async=False)
        else:
            super(SecurityGroupCreationTask, self).execute(security_group, 'create_security_group', *args, **kwargs)
