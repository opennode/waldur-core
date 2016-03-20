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
