from nodeconductor.structure import tasks, executors


class SecurityGroupCreateExecutor(executors.SynchronizableCreateExecutor):

    @classmethod
    def get_tasks(cls, security_group, **kwargs):
        return tasks.BackendMethodTask().si(security_group, 'create_security_group', state_transition='begin_syncing')


class SecurityGroupUpdateExecutor(executors.SynchronizableUpdateExecutor):

    @classmethod
    def get_tasks(cls, security_group, **kwargs):
        return tasks.BackendMethodTask().si(security_group, 'update_security_group', state_transition='begin_syncing')


class SecurityGroupDeleteExecutor(executors.SynchronizableDeleteExecutor):

    @classmethod
    def get_tasks(cls, security_group, **kwargs):
        return tasks.BackendMethodTask().si(security_group, 'delete_security_group', state_transition='begin_syncing')
