from nodeconductor.core import tasks, executors


class ServiceSettingsCreateExecutor(executors.CreateExecutor):

    @classmethod
    def get_task_signature(cls, settings, serialized_settings, **kwargs):
        return tasks.IndependentBackendMethodTask().si(
            serialized_settings, 'sync', state_transition='begin_creating')


class ServiceSettingsPullExecutor(executors.ActionExecutor):

    @classmethod
    def get_task_signature(cls, settings, serialized_settings, **kwargs):
        return tasks.IndependentBackendMethodTask().si(
            serialized_settings, 'sync', state_transition='begin_updating')
