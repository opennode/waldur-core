from celery import chain

from nodeconductor.core import tasks, executors, utils
from nodeconductor.openstack.tasks import delete_tenant_with_spl, SecurityGroupCreationTask


class SecurityGroupCreateExecutor(executors.CreateExecutor):

    @classmethod
    def get_task_signature(cls, security_group, serialized_security_group, **kwargs):
        return SecurityGroupCreationTask().si(
            serialized_security_group, state_transition='begin_creating')


class SecurityGroupUpdateExecutor(executors.UpdateExecutor):

    @classmethod
    def get_task_signature(cls, security_group, serialized_security_group, **kwargs):
        return tasks.BackendMethodTask().si(
            serialized_security_group, 'update_security_group', state_transition='begin_updating')


class SecurityGroupDeleteExecutor(executors.DeleteExecutor):

    @classmethod
    def get_task_signature(cls, security_group, serialized_security_group, **kwargs):
        if security_group.backend_id:
            return tasks.BackendMethodTask().si(
                serialized_security_group, 'delete_security_group', state_transition='begin_deleting')
        else:
            return tasks.StateTransitionTask().si(serialized_security_group, state_transition='begin_deleting')


class TenantCreateExecutor(executors.CreateExecutor):

    @classmethod
    def get_task_signature(cls, tenant, serialized_tenant, pull_security_groups=True, **kwargs):
        # create tenant, add user to it, create internal network, pull quotas
        creation_tasks = [
            tasks.BackendMethodTask().si(
                serialized_tenant, 'create_tenant',
                state_transition='begin_creating',
                runtime_state='creating tenant'),
            tasks.BackendMethodTask().si(
                serialized_tenant, 'add_admin_user_to_tenant',
                runtime_state='adding global admin user to tenant'),
            tasks.BackendMethodTask().si(
                serialized_tenant, 'create_tenant_user',
                runtime_state='creating tenant user'),
            tasks.BackendMethodTask().si(
                serialized_tenant, 'create_internal_network',
                runtime_state='creating internal network for tenant'),
        ]
        quotas = tenant.service_project_link.quotas.all()
        quotas = {q.name: int(q.limit) if q.limit.is_integer() else q.limit for q in quotas}
        creation_tasks.append(tasks.BackendMethodTask().si(
            serialized_tenant, 'push_tenant_quotas', quotas,
            runtime_state='pushing tenant quotas',
            success_runtime_state='online')
        )
        # handle security groups
        # XXX: Create default security groups that was connected to SPL earlier.
        serialized_executor = utils.serialize_class(SecurityGroupCreateExecutor)
        for security_group in tenant.service_project_link.security_groups.all():
            serialized_security_group = utils.serialize_instance(security_group)
            creation_tasks.append(tasks.ExecutorTask().si(serialized_executor, serialized_security_group))

        if pull_security_groups:
            creation_tasks.append(tasks.BackendMethodTask().si(
                serialized_tenant, 'pull_tenant_security_groups',
                runtime_state='pulling tenant security groups',
                success_runtime_state='online')
            )

        # initialize external network if it defined in service settings
        service_settings = tenant.service_project_link.service.settings
        external_network_id = service_settings.options.get('external_network_id')
        if external_network_id:
            creation_tasks.append(tasks.BackendMethodTask().si(
                serialized_tenant, 'connect_tenant_to_external_network',
                external_network_id=external_network_id,
                runtime_state='connecting tenant to external network',
                success_runtime_state='online')
            )

        return chain(*creation_tasks)


class TenantUpdateExecutor(executors.UpdateExecutor):

    @classmethod
    def get_task_signature(cls, tenant, serialized_tenant, **kwargs):
        updated_fields = kwargs['updated_fields']
        if 'name' in updated_fields or 'description' in updated_fields:
            return tasks.BackendMethodTask().si(serialized_tenant, 'update_tenant', state_transition='begin_updating')
        else:
            return tasks.StateTransitionTask().si(serialized_tenant, state_transition='begin_updating')


class TenantDeleteExecutor(executors.DeleteExecutor):

    @classmethod
    def get_task_signature(cls, tenant, serialized_tenant, **kwargs):
        if tenant.backend_id:
            return tasks.BackendMethodTask().si(
                serialized_tenant, 'cleanup_tenant', dryrun=False, state_transition='begin_deleting')
        else:
            return tasks.StateTransitionTask().si(serialized_tenant, state_transition='begin_deleting')


# Temporary. Should be deleted when instance will have direct link to tenant.
class SPLTenantDeleteExecutor(TenantDeleteExecutor):
    """ Delete tenant and SPL together """

    @classmethod
    def get_success_signature(cls, instance, serialized_instance, **kwargs):
        return delete_tenant_with_spl.si(serialized_instance)

    @classmethod
    def get_failure_signature(cls, instance, serialized_instance, force=False, **kwargs):
        return delete_tenant_with_spl.si(serialized_instance)


class TenantAllocateFloatingIPExecutor(executors.ActionExecutor):

    @classmethod
    def get_task_signature(cls, tenant, serialized_tenant, **kwargs):
        return tasks.BackendMethodTask().si(
            serialized_tenant, 'allocate_floating_ip_address',
            state_transition='begin_updating',
            runtime_state='allocating floating ip',
            success_runtime_state='online')


class TenantDeleteExternalNetworkExecutor(executors.ActionExecutor):

    @classmethod
    def get_task_signature(cls, tenant, serialized_tenant, **kwargs):
        return tasks.BackendMethodTask().si(
            serialized_tenant, 'delete_external_network',
            state_transition='begin_updating',
            runtime_state='deleting external network',
            success_runtime_state='online')


class TenantCreateExternalNetworkExecutor(executors.ActionExecutor):

    @classmethod
    def get_task_signature(cls, tenant, serialized_tenant, external_network_data=None, **kwargs):
        if external_network_data is None:
            raise executors.ExecutorException(
                'Argument `external_network_data` should be specified for TenantCreateExcternalNetworkExecutor')
        return tasks.BackendMethodTask().si(
            serialized_tenant, 'create_external_network',
            state_transition='begin_updating',
            runtime_state='creating external network',
            success_runtime_state='online',
            **external_network_data)


class TenantPushQuotasExecutor(executors.ActionExecutor):

    @classmethod
    def get_task_signature(cls, tenant, serialized_tenant, quotas=None, **kwargs):
        return tasks.BackendMethodTask().si(
            serialized_tenant, 'push_tenant_quotas', quotas,
            state_transition='begin_updating',
            runtime_state='updating quotas',
            success_runtime_state='online')


class TenantPullExecutor(executors.ActionExecutor):

    @classmethod
    def get_task_signature(cls, tenant, serialized_tenant, **kwargs):
        return tasks.BackendMethodTask().si(
            serialized_tenant, 'pull_tenant',
            state_transition='begin_updating')


class TenantPullSecurityGroupsExecutor(executors.ActionExecutor):

    @classmethod
    def get_task_signature(cls, tenant, serialized_tenant, **kwargs):
        return tasks.BackendMethodTask().si(
            serialized_tenant, 'pull_tenant_security_groups',
            state_transition='begin_updating')


class TenantDetectExternalNetworkExecutor(executors.ActionExecutor):

    @classmethod
    def get_task_signature(cls, tenant, serialized_tenant, **kwargs):
        return tasks.BackendMethodTask().si(
            serialized_tenant, 'detect_external_network',
            state_transition='begin_updating')


class TenantPullFloatingIPsExecutor(executors.ActionExecutor):

    @classmethod
    def get_task_signature(cls, tenant, serialized_tenant, **kwargs):
        return tasks.BackendMethodTask().si(
            serialized_tenant, 'pull_tenant_floating_ips',
            state_transition='begin_updating')


class TenantPullQuotasExecutor(executors.ActionExecutor):

    @classmethod
    def get_task_signature(cls, tenant, serialized_tenant, **kwargs):
        return tasks.BackendMethodTask().si(
            serialized_tenant, 'pull_tenant_quotas',
            state_transition='begin_updating')
