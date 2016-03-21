from nodeconductor.core import tasks, executors


class SecurityGroupCreateExecutor(executors.CreateExecutor):

    @classmethod
    def get_task_signature(cls, security_group, **kwargs):
        return tasks.BackendMethodTask().si(security_group, 'create_security_group', state_transition='begin_creating')


class SecurityGroupUpdateExecutor(executors.UpdateExecutor):

    @classmethod
    def get_task_signature(cls, security_group, **kwargs):
        return tasks.BackendMethodTask().si(security_group, 'update_security_group', state_transition='begin_updating')


class SecurityGroupDeleteExecutor(executors.DeleteExecutor):

    @classmethod
    def get_task_signature(cls, security_group, **kwargs):
        return tasks.BackendMethodTask().si(security_group, 'delete_security_group', state_transition='begin_deleting')


class TenantCreateExecutor(executors.CreateExecutor):

    @classmethod
    def get_task_signature(cls, tenant, **kwargs):
        creation_tasks = [
            tasks.BackendMethodTask().si(tenant, 'create_tenant', state_transition='begin_creating'),
            tasks.BackendMethodTask().si(tenant, 'add_admin_user_to_tenant'),
            tasks.BackendMethodTask().si(tenant, 'create_internal_network'),
        ]
        service_settings = tenant.service_project_link.service.settings
        external_network_id = service_settings.options.get('external_network_id')
        if external_network_id:
            creation_tasks.append(
                tasks.BackendMethodTask().si(tenant, external_network_id, 'connect_tenant_to_external_network')
            )


class TenantDeleteExecutor(executors.DeleteExecutor):

    @classmethod
    def get_task_signature(cls, tenant, **kwargs):
        return tasks.BackendMethodTask().si(tenant, 'cleanup_tenant', dry_run=False, state_transition='begin_deleting')
