from celery import chain

from nodeconductor.core import tasks, executors


class SecurityGroupCreateExecutor(executors.CreateExecutor):

    @classmethod
    def get_task_signature(cls, security_group, serialized_security_group, **kwargs):
        return tasks.BackendMethodTask().si(
            serialized_security_group, 'create_security_group', state_transition='begin_creating')


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
    def get_task_signature(cls, tenant, serialized_tenant, **kwargs):
        # create tenant, add user to it, create internal network
        creation_tasks = [
            tasks.BackendMethodTask().si(serialized_tenant, 'create_tenant', state_transition='begin_creating'),
            tasks.BackendMethodTask().si(serialized_tenant, 'add_admin_user_to_tenant'),
            tasks.BackendMethodTask().si(serialized_tenant, 'create_internal_network'),
        ]
        # initialize external network if it defined in service settings
        service_settings = tenant.service_project_link.service.settings
        external_network_id = service_settings.options.get('external_network_id')
        if external_network_id:
            creation_tasks.append(tasks.BackendMethodTask().si(
                serialized_tenant, 'connect_tenant_to_external_network', external_network_id=external_network_id)
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
