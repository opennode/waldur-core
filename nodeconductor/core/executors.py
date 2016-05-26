from celery import chord
from celery.worker.job import Request

from nodeconductor.core import utils, tasks


class BaseExecutor(object):
    """ Base class for describing logical operation with backend.

    Executor describes celery signature or primitive of low-level tasks that
    should be executed to provide high-level operation.

    Executor should handle:
     - low-level tasks execution;
     - models state changes;
    """

    @classmethod
    def get_task_signature(cls, instance, serialized_instance, **kwargs):
        """ Get Celery signature or chain that describes executor action.

        Each task should be subclass of LowLevelTask class.
        Celery Signature and Primitives:
         - http://docs.celeryproject.org/en/latest/userguide/canvas.html
        Examples:
         - to execute only one task - return Signature of necessary task: `task.si(serialized_instance)`
         - to execute several tasks - return Chain of tasks: `chain(t1.s(), t2.s())`
        Note! Celery chord and group is not supported. Use BaseChordExecutor for parallel tasks execution.
        """
        raise NotImplementedError('Executor %s should implement method `get_task_signature`' % cls.__name__)

    @classmethod
    def get_success_signature(cls, instance, serialized_instance, **kwargs):
        """ Get Celery signature of task that should be applied on successful execution. """
        return None

    @classmethod
    def get_failure_signature(cls, instance, serialized_instance, **kwargs):
        """ Get Celery signature of task that should be applied on failed execution. """
        return None

    @classmethod
    def execute(cls, instance, async=True, countdown=2, **kwargs):
        """ Execute high level-operation """
        cls.pre_apply(instance, async=async, **kwargs)
        result = cls.apply_signature(instance, async=async, countdown=countdown, **kwargs)
        cls.post_apply(instance, async=async, **kwargs)
        return result

    @classmethod
    def pre_apply(cls, instance, **kwargs):
        """ Perform synchronous actions before signature apply """
        pass

    @classmethod
    def post_apply(cls, instance, **kwargs):
        """ Perform synchronous actions after signature apply """
        pass

    @classmethod
    def apply_signature(cls, instance, async=True, countdown=None, **kwargs):
        """ Serialize input data and apply signature """
        serialized_instance = utils.serialize_instance(instance)
        # TODO: Add ability to serialize kwargs here and deserialize them in task.

        signature = cls.get_task_signature(instance, serialized_instance, **kwargs)
        link = cls.get_success_signature(instance, serialized_instance, **kwargs)
        link_error = cls.get_failure_signature(instance, serialized_instance, **kwargs)

        shadow_name = '.'.join([cls.__module__, cls.__name__])
        for obj in (signature, link, link_error):
            obj.kwargs['_shadow_name'] = shadow_name

        if isinstance(signature.type, tasks.BackendMethodTask):
            try:
                signature.kwargs['_shadow_name'] += ':%s' % signature.args[1]
            except IndexError:
                pass

        if async:
            return signature.apply_async(link=link, link_error=link_error, countdown=countdown)
        else:
            result = signature.apply()
            callback = link if not result.failed() else link_error
            if callback is not None:
                cls._apply_callback(callback, result)

        return result.get()  # wait until task is ready

    @classmethod
    def _apply_callback(cls, callback, result):
        """ Synchronously execute callback """
        if not callback.immutable:
            callback.args = (result.id, ) + callback.args
        callback.apply()


class ExecutorException(Exception):
    pass


class BaseChordExecutor(BaseExecutor):
    """ Allows to use Celery chord for tasks execution.

        Uses tasks from `get_task_signature` method as chord head and
        task from `get_success_signature` - as chord callback.
    """

    @classmethod
    def apply_signature(cls, instance, async=True, countdown=None, **kwargs):
        """ Serialize input data and apply chord """
        if not async:
            raise ExecutorException('Chord executor cannot be executed synchronously')
        serialized_instance = utils.serialize_instance(instance)

        head = cls.get_task_signature(instance, serialized_instance, **kwargs)
        callback = cls.get_success_signature(instance, serialized_instance, **kwargs)
        link_error = cls.get_failure_signature(instance, serialized_instance, **kwargs)

        return chord(head.set(link_error=[link_error]), callback).delay()


class ErrorExecutorMixin(object):
    """ Set object as erred on fail. """

    @classmethod
    def get_failure_signature(cls, instance, serialized_instance, **kwargs):
        return tasks.ErrorStateTransitionTask().s(serialized_instance)


class SuccessExecutorMixin(object):
    """ Set object as OK on success """

    @classmethod
    def get_success_signature(cls, instance, serialized_instance, **kwargs):
        return tasks.StateTransitionTask().si(serialized_instance, state_transition='set_ok')


class DeleteExecutorMixin(object):
    """ Delete object on success or if force flag is enabled """

    @classmethod
    def get_success_signature(cls, instance, serialized_instance, **kwargs):
        return tasks.DeletionTask().si(serialized_instance)

    @classmethod
    def get_failure_signature(cls, instance, serialized_instance, force=False, **kwargs):
        if force:
            return tasks.DeletionTask().si(serialized_instance)
        else:
            return tasks.ErrorStateTransitionTask().s(serialized_instance)


class CreateExecutor(SuccessExecutorMixin, ErrorExecutorMixin, BaseExecutor):
    """ Default states transition for object creation.

     - mark object as OK on success creation;
     - mark object as erred on failed creation;
    """
    pass


class UpdateExecutor(SuccessExecutorMixin, ErrorExecutorMixin, BaseExecutor):
    """ Default states transition for object update.

     - schedule updating before update;
     - mark object as OK on success update;
     - mark object as erred on failed update;
    """

    @classmethod
    def pre_apply(cls, instance, **kwargs):
        instance.schedule_updating()
        instance.save(update_fields=['state'])

    @classmethod
    def execute(cls, instance, async=True, **kwargs):
        if 'updated_fields' not in kwargs:
            raise ExecutorException('updated_fields keyword argument should be defined for UpdateExecutor.')
        super(UpdateExecutor, cls).execute(instance, async=async, **kwargs)


class DeleteExecutor(DeleteExecutorMixin, BaseExecutor):
    """ Default states transition for object deletion.

     - schedule deleting before deletion;
     - delete object on success deletion;
     - mark object as erred on failed deletion;
    """

    @classmethod
    def pre_apply(cls, instance, **kwargs):
        instance.schedule_deleting()
        instance.save(update_fields=['state'])


class ActionExecutor(SuccessExecutorMixin, ErrorExecutorMixin, BaseExecutor):
    """ Default states transition for executing action with object.

     - schedule updating before action execution;
     - mark object as OK on success action execution;
     - mark object as erred on failed action execution;
    """

    @classmethod
    def pre_apply(cls, instance, **kwargs):
        instance.schedule_updating()
        instance.save(update_fields=['state'])


def log_celery_task(task):
    shadow_name = task.kwargs.pop('_shadow_name', '')
    return '{0.name}[{0.id}]{1}{2}{3}'.format(
        task,
        ' name:{0}'.format(shadow_name) if shadow_name else '',
        ' eta:[{0}]'.format(task.eta) if task.eta else '',
        ' expires:[{0}]'.format(task.expires) if task.expires else '',
    )

# XXX: drop the hack and use shadow name in celery 4.0
Request.__str__ = log_celery_task
