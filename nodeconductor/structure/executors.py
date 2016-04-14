from celery import chain

from nodeconductor.core import tasks, executors
from nodeconductor.structure.tasks import ConnectSharedSettingsTask


class ServiceSettingsCreateExecutor(executors.CreateExecutor):

    @classmethod
    def get_task_signature(cls, settings, serialized_settings, **kwargs):
        creation_tasks = [tasks.StateTransitionTask().si(serialized_settings, state_transition='begin_creating')]
        # connect settings to all customers if they are shared
        if settings.shared:
            creation_tasks.append(ConnectSharedSettingsTask().si(serialized_settings))
        # sync settings if they have not only global properties
        backend = settings.get_backend()
        if not backend.has_global_properties():
            creation_tasks.append(tasks.IndependentBackendMethodTask().si(serialized_settings, 'sync'))
        return chain(*creation_tasks)


class ServiceSettingsPullExecutor(executors.ActionExecutor):

    @classmethod
    def get_task_signature(cls, settings, serialized_settings, **kwargs):
        return tasks.IndependentBackendMethodTask().si(
            serialized_settings, 'sync', state_transition='begin_updating')


class ServiceSettingsConnectSharedExecutor(executors.BaseExecutor):

    @classmethod
    def get_task_signature(cls, settings, serialized_settings, **kwargs):
        return ConnectSharedSettingsTask().si(serialized_settings)
