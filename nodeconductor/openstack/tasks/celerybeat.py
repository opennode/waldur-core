from nodeconductor.core import tasks as core_tasks, utils as core_utils
from nodeconductor.openstack import models


def pull_tenants_properties():
    for tenant in models.Tenant.objects.filter(state=models.Tenant.States.OK):
        serialized_tenant = core_utils.serialize_instance(tenant)
        # XXX: It is unsafe to pull security groups like without any checks.
        #      This can lead to conflicts with user updates in case of
        #      simultaneous operations. (Issue NC-1275)
        core_tasks.BackendMethodTask().delay(serialized_tenant, 'pull_tenant_security_groups')
        core_tasks.BackendMethodTask().delay(serialized_tenant, 'pull_tenant_floating_ips')
        core_tasks.BackendMethodTask().delay(serialized_tenant, 'pull_tenant_quotas')
