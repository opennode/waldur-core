from nodeconductor.core import utils as core_utils
from nodeconductor.structure import tasks


class BaseExecutor(object):
    """ Base class that corresponds logical operation with backend.

    Executor describes celery signature or primitive of low-level tasks that
    should be executed to provide high-level operation.

    Executor should handle:
     - low-level tasks execution;
     - models state changes;
    """

    @classmethod
    def get_task_signature(cls, serialized_instance, **kwargs):
        """ Get Celery signature or primitive that describes executor action.

        Each task should be subclass of LowLevelTask class.
        Celery Signature and Primitives:
         - http://docs.celeryproject.org/en/latest/userguide/canvas.html
        Examples:
         - to execute only one task - return Signature of necessary task: `task.si(serialized_instance)`
         - to execute several tasks - return Chain, Chord or Group of tasks: `chain(t1.s(), t2.s())`
        """
        raise NotImplementedError('Executor %s should implement method `get_tasks`' % cls.__name__)

    @classmethod
    def get_success_signature(cls, serialized_instance, **kwargs):
        """ Get Celery signature of task that should be applied on successful execution. """
        return None

    @classmethod
    def get_failure_signature(cls, serialized_instance, **kwargs):
        """ Get Celery signature of task that should be applied on failed execution. """
        return None

    @classmethod
    def execute(cls, instance, async=True, **kwargs):
        """ Execute high level-operation """
        cls.pre_apply(instance, async=async, **kwargs)
        result = cls.apply_tasks(instance, async=async, **kwargs)
        cls.post_apply(instance, async=async, **kwargs)
        return result

    @classmethod
    def pre_apply(cls, instance, async=True, **kwargs):
        """ Perform synchronous actions before tasks apply """
        pass

    @classmethod
    def post_apply(cls, instance, async=True, **kwargs):
        """ Perform synchronous actions after tasks apply """
        pass

    @classmethod
    def apply_signature(cls, instance, async=True, **kwargs):
        """ Serialize input data and apply tasks """
        serialized_instance = core_utils.serialize_instance(instance)
        # TODO: Add ability to serialize kwargs here and deserialize them in task.

        tasks = cls.get_tasks(serialized_instance, **kwargs)
        link = cls.get_success_signature(serialized_instance, **kwargs),
        link_error = cls.get_failure_signature(serialized_instance, **kwargs)

        if async:
            return tasks.apply_async(link=link, link_error=link_error)
        else:
            result = tasks.apply()
            callback = link if not result.failed() else link_error
            if callback is not None:
                cls._apply_callback(callback, result)

        return result

    @classmethod
    def _apply_callback(cls, callback, result):
        """ Synchronously execute callback """
        if not callback.immutable:
            callback.args = (result.id, ) + callback.args
        callback.apply()


class ErrorExecutorMixin(object):
    """ Set object as erred on fail. """

    @classmethod
    def get_failure_signature(cls, serialized_instance, **kwargs):
        return tasks.ErrorStateTransitionTask().s(serialized_instance)


class DeleteExecutorMixin(object):
    """ Delete object on success """

    @classmethod
    def get_success_signature(cls, serialized_instance, **kwargs):
        return tasks.DeletionTask().si(serialized_instance)


class SynchronizableExecutorMixin(object):
    """ Set object in sync on success """

    @classmethod
    def get_success_signature(cls, serialized_instance, **kwargs):
        return tasks.StateTransitionTask().si(serialized_instance, state_transition='set_in_sync')


class SynchronizableCreateExecutor(SynchronizableExecutorMixin, ErrorExecutorMixin, BaseExecutor):
    """ Default states transition for Synchronizable object creation.

     - set object in sync on success creation;
     - mark object as erred on failed creation;
    """
    pass


class SynchronizableUpdateExecutor(SynchronizableExecutorMixin, ErrorExecutorMixin, BaseExecutor):
    """ Default states transition for Synchronizable object update.

     - schedule syncing before update;
     - set object in sync on success update;
     - mark object as erred on failed update;
    """

    @classmethod
    def pre_apply(cls, instance, async=True, **kwargs):
        instance.schedule_syncing()
        instance.save(update_fields=['state'])


class SynchronizableDeleteExecutor(DeleteExecutorMixin, ErrorExecutorMixin, BaseExecutor):
    """ Default states transition for Synchronizable object deletion.

     - schedule syncing before deletion;
     - delete object on success deletion;
     - mark object as erred on failed deletion;
    """

    @classmethod
    def pre_apply(cls, instance, async=True, **kwargs):
        instance.schedule_syncing()
        instance.save(update_fields=['state'])
