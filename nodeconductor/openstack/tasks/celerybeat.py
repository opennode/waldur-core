from celery import shared_task, chain

from nodeconductor.core import tasks as core_tasks, utils as core_utils
from nodeconductor.openstack import models


@shared_task(name='nodeconductor.openstack.pull_tenants')
def pull_tenants():
    # XXX: It is unsafe to pull tenant without any checks.
    #      This can lead to conflicts with user updates in case of
    #      simultaneous operations. (Issue NC-1275)
    for tenant in models.Tenant.objects.filter(state=models.Tenant.States.ERRED):
        serialized_tenant = core_utils.serialize_instance(tenant)
        core_tasks.BackendMethodTask().apply_async(
            args=(serialized_tenant, 'pull_tenant'),
            link=recover_tenant.si(serialized_tenant),
            link_error=core_tasks.ErrorMessageTask().s(serialized_tenant),
        )
    for tenant in models.Tenant.objects.filter(state=models.Tenant.States.OK):
        serialized_tenant = core_utils.serialize_instance(tenant)
        core_tasks.BackendMethodTask().delay(serialized_tenant, 'pull_tenant')


@shared_task
def recover_tenant(serialized_tenant):
    chain(
        core_tasks.StateTransitionTask().si(serialized_tenant, state_transition='recover'),
        core_tasks.BackendMethodTask().si(serialized_tenant, 'pull_tenant_security_groups'),
        core_tasks.BackendMethodTask().si(serialized_tenant, 'pull_tenant_floating_ips'),
        core_tasks.BackendMethodTask().si(serialized_tenant, 'pull_tenant_quotas'),
    ).delay()


@shared_task(name='nodeconductor.openstack.pull_tenants_properties')
def pull_tenants_properties():
    for tenant in models.Tenant.objects.filter(state=models.Tenant.States.OK):
        serialized_tenant = core_utils.serialize_instance(tenant)
        # XXX: It is unsafe to pull security groups without any checks.
        #      This can lead to conflicts with user updates in case of
        #      simultaneous operations. (Issue NC-1275)
        core_tasks.BackendMethodTask().delay(serialized_tenant, 'pull_tenant_security_groups')
        core_tasks.BackendMethodTask().delay(serialized_tenant, 'pull_tenant_floating_ips')
        core_tasks.BackendMethodTask().delay(serialized_tenant, 'pull_tenant_quotas')
        core_tasks.BackendMethodTask().delay(serialized_tenant, 'pull_tenant_instances')
