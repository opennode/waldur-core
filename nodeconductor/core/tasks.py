from __future__ import unicode_literals

import functools
import logging
import sys

from celery import current_app, current_task, Task as CeleryTask
from celery.execute import send_task as send_celery_task
from celery.exceptions import MaxRetriesExceededError
from django.conf import settings
from django.db import transaction, IntegrityError, models as django_models
from django.db.models import ObjectDoesNotExist
from django.utils import six
from django_fsm import TransitionNotAllowed

from nodeconductor.core import models, utils


logger = logging.getLogger(__name__)


class Throttled(RuntimeError):
    pass


class StateChangeError(RuntimeError):
    pass


class Throttle(object):
    """ Limit a number of celery tasks running in parallel.
        Retry task until conditions meet or timeout exceed.

        An instance can be used either as a decorator or as a context manager.

        .. code-block:: python
            @shared_task(name="change_instance")
            def change_instance1(instance_uuid):
                instance = Instance.objects.get(uuid=instance_uuid)
                with throttle(key=instance.service_project_link.service.settings.backend_url):
                    instance.change_instance()

            @shared_task()
            @throttle(concurrency=3)
            def change_instance2(instance_uuid):
                instance = Instance.objects.get(uuid=instance_uuid)
                instance.change_instance()

        :param key: an additional key to be used with task name
        :param concurrency: a number of tasks running at once
        :param retry_delay: a time in seconds before the next try
        :param timeout: a time in seconds to keep a lock

        Concurrency and other options can be set via django settings:

        .. code-block:: python
            CELERY_TASK_THROTTLING = {
                'change_instance': {
                    'concurrency': 2,
                    'retry_delay': 60,
                    'timeout': 2 * 3600,
                },
            }

        But these settings have lower priority and will be used only when
        they omitted during task definition.
    """

    DEFAULT_OPTIONS = {
        'concurrency': 1,
        'retry_delay': 30,
        'timeout': 3600,
    }

    def __init__(self, key='*', **kwargs):
        self.set_options(**kwargs)
        self.task_name = None
        self.task_key = key

    def __enter__(self):
        if self.acquire_lock():
            return self

        try:
            # max_retries should be big enough to retry until lock expired
            # this guaranties that task will be executed rather than failed
            current_task.retry(countdown=self.opt('retry_delay'), max_retries=10000)
        except MaxRetriesExceededError as e:
            six.reraise(Throttled, e)

    def __exit__(self, exc_type, exc_value, traceback):
        self.release_lock()

    def __call__(self, task_fn):
        @functools.wraps(task_fn)
        def inner(*args, **kwargs):
            self.set_options()
            self.task_name = current_task.name
            with self:
                return task_fn(*args, **kwargs)
        return inner

    def set_options(self, **kwargs):
        conf = {}
        if current_task:
            conf = getattr(settings, 'CELERY_TASK_THROTTLING', {}).get(current_task.name, {})

        for opt_name in self.DEFAULT_OPTIONS:
            opt_val = getattr(self, opt_name, None) or kwargs.get(opt_name) or conf.get(opt_name)
            setattr(self, opt_name, opt_val)

    def opt(self, opt_name):
        return getattr(self, opt_name, None) or self.DEFAULT_OPTIONS.get(opt_name)

    @property
    def key(self):
        if not self.task_name:
            self.task_name = current_task.name
        return 'nc:{}:{}'.format(self.task_name, self.task_key)

    @property
    def redis(self):
        return current_app.backend.client

    def acquire_lock(self):
        concurrency = self.opt('concurrency')
        currently_running = self.redis.get(self.key) or 0
        if int(currently_running) >= int(concurrency):
            logger.debug('Tasks limit exceed for %s, limit: %s', self.key, concurrency)
            return False

        pipe = self.redis.pipeline()
        pipe.incr(self.key)
        pipe.expire(self.key, self.opt('timeout'))
        pipe.execute()
        logger.debug('Acquire lock for %s, total: %s', self.key, currently_running)
        return True

    def release_lock(self):
        pipe = self.redis.pipeline()
        pipe.decr(self.key)
        pipe.expire(self.key, self.opt('timeout'))
        pipe.execute()
        logger.debug('Release lock for %s, remaining: %s', self.key, self.redis.get(self.key))
        return True


def throttle(*args, **kwargs):
    if args and callable(args[0]):
        return Throttle(**kwargs)(args[0])
    return Throttle(*args, **kwargs)


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
    """ Execute only instance state transition """

    def state_transition(self, instance, transition_method):
        instance_description = '%s instance `%s` (PK: %s)' % (instance.__class__.__name__, instance, instance.pk)
        old_state = instance.human_readable_state
        try:
            getattr(instance, transition_method)()
            instance.save(update_fields=['state'])
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
        if state_transition is not None:
            self.state_transition(instance, state_transition)
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

    def execute(self, instance):
        instance_description = '%s instance `%s` (PK: %s)' % (instance.__class__.__name__, instance, instance.pk)
        instance.delete()
        logger.info('%s was successfully deleted', instance_description)


class ErrorMessageTask(Task):
    """ Store error in error_message field.

    This task should not be called as immutable, because it expects result_uuid
    as input argument.
    """
    def run(self, result_id, serialized_instance, *args, **kwargs):
        self.result = self.AsyncResult(result_id)
        return super(ErrorMessageTask, self).run(serialized_instance, *args, **kwargs)

    def save_error_message(self, instance):
        if isinstance(instance, models.ErrorMessageMixin):
            instance.error_message = self.result.result
            instance.save(update_fields=['error_message'])

    def execute(self, instance):
        self.save_error_message(instance)


class ErrorStateTransitionTask(ErrorMessageTask, StateTransitionTask):
    """ Set instance as erred and save error message.

    This task should not be called as immutable, because it expects result_uuid
    as input argument.
    """
    def execute(self, instance):
        self.state_transition(instance, 'set_erred')
        self.save_error_message(instance)


class RecoverTask(StateTransitionTask):
    """ Change instance state from ERRED to OK and clear error_message """

    def execute(self, instance):
        self.state_transition(instance, 'recover')
        instance.error_message = ''
        instance.save(update_fields=['error_message'])


class ExecutorTask(Task):
    """ Run executor as a task """

    def run(self, serialized_executor, serialized_instance, *args, **kwargs):
        self.executor = utils.deserialize_class(serialized_executor)
        return super(ExecutorTask, self).run(serialized_instance, *args, **kwargs)

    def execute(self, instance, **kwargs):
        self.executor.execute(instance, async=False, **kwargs)
