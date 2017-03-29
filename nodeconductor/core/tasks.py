from __future__ import unicode_literals

import functools
import json
import hashlib
import logging
import sys

from celery import current_task, Task as CeleryTask
from celery.execute import send_task as send_celery_task
from celery.exceptions import MaxRetriesExceededError
from celery.worker.job import Request
from django.core.cache import cache
from django.db import transaction, IntegrityError, models as django_models
from django.db.models import ObjectDoesNotExist
from django.utils import six
from django_fsm import TransitionNotAllowed

from nodeconductor.core import models, utils


logger = logging.getLogger(__name__)


class StateChangeError(RuntimeError):
    pass


def transition(model_class, processing_state, error_state='set_erred'):
    """ Atomically runs state transition for a model_class instance.
        Executes desired task on success.
    """
    def decorator(task_fn):
        @functools.wraps(task_fn)
        def wrapped(uuid_or_pk, *task_args, **task_kwargs):
            logged_operation = processing_state.replace('_', ' ')
            entity_name = model_class._meta.model_name

            try:
                with transaction.atomic():
                    if 'uuid' in model_class._meta.get_all_field_names():
                        kwargs = {'uuid': uuid_or_pk}
                    else:
                        kwargs = {'pk': uuid_or_pk}
                    entity = model_class._default_manager.get(**kwargs)

                    getattr(entity, processing_state)()
                    entity.save(update_fields=['state'])

            except model_class.DoesNotExist as e:
                logger.error(
                    'Could not %s %s with id %s. Instance has gone',
                    logged_operation, entity_name, uuid_or_pk)

                six.reraise(StateChangeError, e)

            except IntegrityError as e:
                logger.error(
                    'Could not %s %s with id %s due to concurrent update',
                    logged_operation, entity_name, uuid_or_pk)

                six.reraise(StateChangeError, e)

            except TransitionNotAllowed as e:
                logger.error(
                    'Could not %s %s with id %s, transition not allowed',
                    logged_operation, entity_name, uuid_or_pk)

                six.reraise(StateChangeError, e)

            else:
                logger.info(
                    'Managed to %s %s with id %s',
                    logged_operation, entity_name, uuid_or_pk)

                try:
                    task_kwargs['transition_entity'] = entity
                    return task_fn(uuid_or_pk, *task_args, **task_kwargs)
                except:
                    getattr(entity, error_state)()
                    entity.save(update_fields=['state'])
                    logger.error(
                        'Failed to finish task %s after %s %s with id %s',
                        task_fn.__name__, logged_operation, entity_name, uuid_or_pk)
                    raise

        return wrapped
    return decorator


def save_error_message(func):
    """
    This function will work only if transition_entity is defined in kwargs and
    transition_entity is instance of ErrorMessageMixin
    """
    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as exception:
            message = six.text_type(exception)
            transition_entity = kwargs['transition_entity']
            if message:
                transition_entity.error_message = message
                transition_entity.save(update_fields=['error_message'])
            six.reraise(*sys.exc_info())
    return wrapped


def retry_if_false(func):
    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        is_true = func(*args, **kwargs)
        if not is_true:
            try:
                current_task.retry()
            except MaxRetriesExceededError:
                raise RuntimeError('Task %s failed to retry' % current_task.name)

        return is_true
    return wrapped


def send_task(app_label, task_name):
    """ A helper function to deal with nodeconductor "high-level" tasks.
        Define high-level task with explicit name using a pattern:
        nodeconductor.<app_label>.<task_name>

        .. code-block:: python
            @shared_task(name='nodeconductor.openstack.provision_instance')
            def provision_instance_fn(instance_uuid, backend_flavor_id)
                pass

        Call it by name:

        .. code-block:: python
            send_task('openstack', 'provision_instance')(instance_uuid, backend_flavor_id)

        Which is identical to:

        .. code-block:: python
            provision_instance_fn.delay(instance_uuid, backend_flavor_id)

    """

    def delay(*args, **kwargs):
        full_task_name = 'nodeconductor.%s.%s' % (app_label, task_name)
        send_celery_task(full_task_name, args, kwargs, countdown=2)

    return delay


class Task(CeleryTask):
    """ Base class for tasks that are run by executors.

    Provides standard way for input data deserialization.
    """

    @classmethod
    def get_description(cls, *args, **kwargs):
        """ Add additional information about task to celery logs.

            Receives same parameters as method "run".
        """
        raise NotImplementedError()

    def run(self, serialized_instance, *args, **kwargs):
        """ Deserialize input data and start backend operation execution """
        try:
            instance = utils.deserialize_instance(serialized_instance)
        except ObjectDoesNotExist:
            message = ('Cannot restore instance from serialized object %s. Probably it was deleted.' %
                       serialized_instance)
            six.reraise(ObjectDoesNotExist, message)

        self.args = args
        self.kwargs = kwargs

        self.pre_execute(instance)
        result = self.execute(instance, *self.args, **self.kwargs)
        self.post_execute(instance)
        if result and isinstance(result, django_models.Model):
            result = utils.serialize_instance(result)
        return result

    def pre_execute(self, instance):
        pass

    def execute(self, instance, *args, **kwargs):
        """ Execute backend operation """
        raise NotImplementedError('%s should implement method `execute`' % self.__class__.__name__)

    def post_execute(self, instance):
        pass


class EmptyTask(CeleryTask):

    def run(self, *args, **kwargs):
        pass


class StateTransitionTask(Task):
    """ Execute instance state transition, changes instance action and action details if defined.

        It is impossible to change object action without state transition.
    """

    @classmethod
    def get_description(cls, instance, *args, **kwargs):
        transition_method = kwargs.get('state_transition')
        return 'Change state of object "%s" using method "%s".' % (instance, transition_method)

    def state_transition(self, instance, transition_method, action=None, action_details=None):
        instance_description = '%s instance `%s` (PK: %s)' % (instance.__class__.__name__, instance, instance.pk)
        old_state = instance.human_readable_state
        try:
            getattr(instance, transition_method)()
            if action is not None:
                instance.action = action
            if action_details is not None:
                instance.action_details = action_details
            instance.save()
        except IntegrityError:
            message = (
                'Could not change state of %s, using method `%s` due to concurrent update' %
                (instance_description, transition_method))
            six.reraise(StateChangeError, StateChangeError(message))
        except TransitionNotAllowed:
            message = (
                'Could not change state of %s, using method `%s`. Current instance state: %s.' %
                (instance_description, transition_method, instance.human_readable_state))
            six.reraise(StateChangeError, StateChangeError(message))
        else:
            logger.info('State of %s changed from %s to %s, with method `%s`',
                        instance_description, old_state, instance.human_readable_state, transition_method)

    def pre_execute(self, instance):
        state_transition = self.kwargs.pop('state_transition', None)
        action = self.kwargs.pop('action', None)
        action_details = self.kwargs.pop('action_details', None)
        if state_transition is not None:
            self.state_transition(instance, state_transition, action, action_details)
        super(StateTransitionTask, self).pre_execute(instance)

    # Empty execute method allows to use StateTransitionTask as standalone task
    def execute(self, instance, *args, **kwargs):
        return instance


class RuntimeStateChangeTask(Task):
    """ Allows to change runtime state of instance before and after execution.

    Define kwargs:
     - runtime_state - to change instance runtime state during execution.
     - success_runtime_state - to change instance runtime state after success tasks execution.
    """
    @classmethod
    def get_description(cls, instance, *args, **kwargs):
        runtime_state = kwargs.get('runtime_state')
        return 'Change runtime state of object "%s" to "%s".' % (instance, runtime_state)

    def update_runtime_state(self, instance, runtime_state):
        instance.runtime_state = runtime_state
        instance.save(update_fields=['runtime_state'])

    def pre_execute(self, instance):
        self.runtime_state = self.kwargs.pop('runtime_state', None)
        self.success_runtime_state = self.kwargs.pop('success_runtime_state', None)

        if self.runtime_state is not None:
            self.update_runtime_state(instance, self.runtime_state)
        super(RuntimeStateChangeTask, self).pre_execute(instance)

    def post_execute(self, instance, *args, **kwargs):
        if self.success_runtime_state is not None:
            self.update_runtime_state(instance, self.success_runtime_state)
        super(RuntimeStateChangeTask, self).post_execute(instance)

    # Empty execute method allows to use RuntimeStateChangeTask as standalone task
    def execute(self, instance, *args, **kwargs):
        return instance


class BackendMethodTask(RuntimeStateChangeTask, StateTransitionTask):
    """ Execute method of instance backend """
    @classmethod
    def get_description(cls, instance, backend_method, *args, **kwargs):
        actions = ['Run backend method "%s" for instance "%s".' % (backend_method, instance)]
        if 'state_transition' in kwargs:
            actions.append(StateTransitionTask.get_description(instance, backend_method, *args, **kwargs))
        if 'runtime_state' in kwargs:
            actions.append(RuntimeStateChangeTask.get_description(instance, backend_method, *args, **kwargs))
        return ' '.join(actions)

    def get_backend(self, instance):
        return instance.get_backend()

    def execute(self, instance, backend_method, *args, **kwargs):
        backend = self.get_backend(instance)
        return getattr(backend, backend_method)(instance, *args, **kwargs)


class IndependentBackendMethodTask(BackendMethodTask):
    """ Execute instance backend method that does not receive instance as argument """

    def execute(self, instance, backend_method, *args, **kwargs):
        backend = self.get_backend(instance)
        return getattr(backend, backend_method)(*args, **kwargs)


class DeletionTask(Task):
    """ Delete instance """
    @classmethod
    def get_description(cls, *args, **kwargs):
        instance = args[0]
        return 'Delete instance "%s".' % instance

    def execute(self, instance):
        instance_description = '%s instance `%s` (PK: %s)' % (instance.__class__.__name__, instance, instance.pk)
        instance.delete()
        logger.info('%s was successfully deleted', instance_description)


class ErrorMessageTask(Task):
    """ Store error in error_message field.

    This task should not be called as immutable, because it expects result_uuid
    as input argument.
    """
    @classmethod
    def get_description(cls, result_id, instance, *args, **kwargs):
        return 'Add error message to instance "%s".' % instance

    def run(self, result_id, serialized_instance, *args, **kwargs):
        self.result = self.AsyncResult(result_id)
        return super(ErrorMessageTask, self).run(serialized_instance, *args, **kwargs)

    def save_error_message(self, instance):
        if isinstance(instance, models.ErrorMessageMixin):
            instance.error_message = self.result.result
            instance.save(update_fields=['error_message'])
            # log exception if instance is not already ERRED.
            if instance.state != models.StateMixin.States.ERRED:
                message = 'Error: %s.\n' % self.result.result
                message += self.result.traceback
                logger.exception(message)

    def execute(self, instance):
        self.save_error_message(instance)


class ErrorStateTransitionTask(ErrorMessageTask, StateTransitionTask):
    """ Set instance as erred and save error message.

    This task should not be called as immutable, because it expects result_uuid
    as input argument.
    """
    @classmethod
    def get_description(cls, result_id, instance, *args, **kwargs):
        return 'Add error message and set erred instance "%s".' % instance

    def execute(self, instance):
        self.save_error_message(instance)
        self.state_transition(instance, 'set_erred', action='', action_details={})


class RecoverTask(StateTransitionTask):
    """ Change instance state from ERRED to OK and clear error_message """
    @classmethod
    def get_description(cls, instance, *args, **kwargs):
        return 'Recover instance "%s".' % instance

    def execute(self, instance):
        self.state_transition(instance, 'recover')
        instance.error_message = ''
        instance.save(update_fields=['error_message'])


class ExecutorTask(Task):
    """ Run executor as a task """
    @classmethod
    def get_description(cls, executor, instance, *args, **kwargs):
        return 'Run executor "%s" for instance "%s".' % (executor, instance)

    def run(self, serialized_executor, serialized_instance, *args, **kwargs):
        self.executor = utils.deserialize_class(serialized_executor)
        return super(ExecutorTask, self).run(serialized_instance, *args, **kwargs)

    def execute(self, instance, **kwargs):
        self.executor.execute(instance, async=False, **kwargs)


class BackgroundTask(CeleryTask):
    """ Task that is run in background via celerybeat.

        Background task features:
         - background task does not start if previous task with the same name
           and input parameters is not completed yet;
         - all background tasks are scheduled in separate queue "background";
         - by default we do not log background tasks in celery logs. So tasks
           should log themselves explicitly and make sure that they will not
           spam error messages.

        Implement "is_equal" method to define what tasks are equal and should
        be executed simultaneously.
    """
    is_background = True

    def is_equal(self, other_task, *args, **kwargs):
        """ Return True if task do the same operation as other_task.

            Note! Other task is represented as serialized celery task - dictionary.
        """
        raise NotImplementedError('BackgroundTask should implement "is_equal" method to avoid queue overload.')

    def is_previous_task_processing(self, *args, **kwargs):
        """ Return True if exist task that is equal to current and is uncompleted """
        app = self._get_app()
        inspect = app.control.inspect()
        active = inspect.active() or {}
        scheduled = inspect.scheduled() or {}
        reserved = inspect.reserved() or {}
        uncompleted = sum(active.values() + scheduled.values() + reserved.values(), [])
        return any(self.is_equal(task, *args, **kwargs) for task in uncompleted)

    def apply_async(self, args=None, kwargs=None, **options):
        """ Do not run background task if previous task is uncompleted """
        if self.is_previous_task_processing(*args, **kwargs):
            message = 'Background task %s was not scheduled, because its predecessor is not completed yet.' % self.name
            logger.info(message)
            return
        return super(BackgroundTask, self).apply_async(args=args, kwargs=kwargs, **options)


class PenalizedBackgroundTask(BackgroundTask):
    """
    Background task, which applies penalties in case of failed execution.
    It uses cache memory for tracking results of previous task executions.
    The following values are stored to the cache memory:
        - counter - the task will be skipped till the counter gets 0.
        - penalty - shows how much runs the task will skip in case of failed execution.

    For example,
    1 run: Cache state: Empty; Result: failed
    2 run: Cache state: counter = 1, penalty = 1; Result: skipped
    3 run: Cache state: counter = 0, penalty = 1; Result: failed
    4 run: Cache state: counter = 2, penalty = 2; Result: skipped
    5 run: Cache state: counter = 1, penalty = 2; Result: skipped
    6 run: Cache state: counter = 0, penalty = 2; Result: success
    7 run: Cache state: Empty; Result: success

    NB! Ensure that CACHE_LIFETIME is longer than time between the task executions.
    """

    MAX_PENALTY = 3
    CACHE_LIFETIME = 24 * 60 * 60

    def _get_cache_key(self, args, kwargs):
        """ Returns key to be used in cache """
        hash_input = json.dumps({'name': self.name, 'args': args, 'kwargs': kwargs}, sort_keys=True)
        # md5 is used for internal caching, not need to care about security
        return hashlib.md5(hash_input).hexdigest()  # nosec

    def apply_async(self, args=None, kwargs=None, **options):
        """
        Checks whether task must be skipped and decreases the counter in that case.
        """
        key = self._get_cache_key(args, kwargs)
        counter, penalty = cache.get(key, (0, 0))
        if not counter:
            return super(PenalizedBackgroundTask, self).apply_async(args=args, kwargs=kwargs, **options)

        cache.set(key, (counter - 1, penalty), self.CACHE_LIFETIME)
        logger.info('The task %s will not be executed due to the penalty.' % self.name)
        return self.AsyncResult(options.get('task_id'))

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """
        Increases penalty for the task and resets the counter.
        """
        key = self._get_cache_key(args, kwargs)
        _, penalty = cache.get(key, (0, 0))
        if penalty < self.MAX_PENALTY:
            penalty += 1

        logger.debug('The task %s is penalized and will be executed on %d run.' % (self.name, penalty))
        cache.set(key, (penalty, penalty), self.CACHE_LIFETIME)
        return super(PenalizedBackgroundTask, self).on_failure(exc, task_id, args, kwargs, einfo)

    def on_success(self, retval, task_id, args, kwargs):
        """
        Clears cache for the task.
        """
        key = self._get_cache_key(args, kwargs)
        if cache.get(key) is not None:
            cache.delete(key)
            logger.debug('Penalty for the task %s has been removed.' % self.name)

        return super(PenalizedBackgroundTask, self).on_success(retval, task_id, args, kwargs)


def log_celery_task(request):
    """ Add description to celery log output """
    task = request.task
    description = None
    if isinstance(task, Task):
        try:
            description = task.get_description(*request.args, **request.kwargs)
        except NotImplementedError:
            pass
        except Exception as e:
            # Logging should never break workflow.
            logger.exception('Cannot get description for task %s. Error: %s' % (task.__class__.__name__, e))

    return '{0.name}[{0.id}]{1}{2}{3}'.format(
        request,
        ' {0}'.format(description) if description else '',
        ' eta:[{0}]'.format(request.eta) if request.eta else '',
        ' expires:[{0}]'.format(request.expires) if request.expires else '',
    )


# XXX: drop the hack and use shadow name in celery 4.0
Request.__str__ = log_celery_task
