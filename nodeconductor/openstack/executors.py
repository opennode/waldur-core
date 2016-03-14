from nodeconductor.structure.tasks import DeleteExecutor, SyncExecutor, BackendMethodTask


class SecurityGroupCreateExecutor(SyncExecutor):

    @classmethod
    def get_tasks(self, security_group, **kwargs):
        return BackendMethodTask().si(security_group, 'create_security_group', state_transition='begin_syncing')


class SecurityGroupUpdateExecutor(SyncExecutor):

    @classmethod
    def pre_execute(self, security_group, **kwargs):
        security_group.schedule_syncing()
        security_group.save()

    @classmethod
    def get_tasks(self, security_group, **kwargs):
        return BackendMethodTask().si(security_group, 'update_security_group', state_transition='begin_syncing')


class SecurityGroupDeleteExecutor(DeleteExecutor):

    @classmethod
    def pre_execute(self, security_group, **kwargs):
        security_group.schedule_syncing()
        security_group.save()

    @classmethod
    def get_tasks(self, security_group, **kwargs):
        return BackendMethodTask().si(security_group, 'delete_security_group', state_transition='begin_syncing')
