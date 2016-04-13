from celery import chain

from nodeconductor.core import tasks, executors
from nodeconductor.structure.tasks import ConnectSharedSettingsTask


class ServiceSettingsCreateExecutor(executors.CreateExecutor):

    @classmethod
    def get_task_signature(cls, settings, serialized_settings, **kwargs):
        creation_tasks = []
        if settings.shared:
            creation_tasks.append(ConnectSharedSettingsTask().si(serialized_settings))
        creation_tasks.append(tasks.IndependentBackendMethodTask().si(
            serialized_settings, 'sync', state_transition='begin_creating')
        )
        return chain(*creation_tasks)


class ServiceSettingsPullExecutor(executors.ActionExecutor):

    @classmethod
    def get_task_signature(cls, settings, serialized_settings, **kwargs):
        return tasks.IndependentBackendMethodTask().si(
            serialized_settings, 'sync', state_transition='begin_updating')


class ServiceSettingsConnectSharedExecutor(executors.ActionExecutor):

    @classmethod
    def get_task_signature(cls, settings, serialized_settings, **kwargs):
        return ConnectSharedSettingsTask().si(serialized_settings)
