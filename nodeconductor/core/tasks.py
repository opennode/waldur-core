from __future__ import unicode_literals

import functools
import logging
import sys

from django.db import transaction, IntegrityError, DatabaseError
from django.conf import settings
from django.utils import six
from django_fsm import TransitionNotAllowed

from celery import current_app, current_task
from celery.execute import send_task as send_celery_task
from celery.exceptions import MaxRetriesExceededError


logger = logging.getLogger(__name__)


class Throttled(RuntimeError):
    pass


class StateChangeError(RuntimeError):
    pass


# noinspection PyProtectedMember
def set_state(model_class, uuid_or_pk, transition):
    """
    Atomically change state of a model_class instance.

    Handles edge cases:
    * model instance missing in the database
    * concurrent database update of a model instance
    * model instance being in a state that forbids transition

    Raises StateChangeError in case of any of the above.

    Example:

    .. code-block:: python
        # models.py
        from django.db import models
        from nodeconductor.core.models import UuidMixin


        class Worker(UuidMixin, models.Model):
            state = FSMField(default='idle')

            @transition(field=state, source='idle', target='working')
            def start_working(self):
                pass

        # views.py
        from django.shortcuts import render_to_response
        from . import models


        def begin_work(worker_uuid):
            try:
                set_state(models.Worker, worker_uuid, 'start_working')
            except StateChangeError:
                return render_to_response('failed to start working')
            else:
                return render_to_response('started working')

    :param model_class: model class of an instance to change state
    :type model_class: django.db.models.Model
    :param uuid_or_pk: identifier of the model_class instance
    :param transition: name of model's method to trigger transition
    :type transition: str
    :raises: StateChangeError
    """
    logged_operation = transition.replace('_', ' ')
    entity_name = model_class._meta.model_name

    logger.info(
        'About to %s %s with id %s',
        logged_operation, entity_name, uuid_or_pk
    )

    try:
        with transaction.atomic():
            if 'uuid' in model_class._meta.get_all_field_names():
                kwargs = {'uuid': uuid_or_pk}
            else:
                kwargs = {'pk': uuid_or_pk}
            entity = model_class._default_manager.get(**kwargs)

            # TODO: Make sure that the transition method actually exists
            transition = getattr(entity, transition)
            transition()

            entity.save()
    except model_class.DoesNotExist:
        # There's nothing we can do here to save the state of an entity
        logger.error(
            'Could not %s %s with id %s. Instance has gone',
            logged_operation, entity_name, uuid_or_pk)

        six.reraise(StateChangeError, StateChangeError())
    except DatabaseError:
        # Transaction failed to commit, most likely due to concurrent update
        logger.error(
            'Could not %s %s with id %s due to concurrent update',
            logged_operation, entity_name, uuid_or_pk)

        six.reraise(StateChangeError, StateChangeError())
    except TransitionNotAllowed:
        # Leave the entity intact
        logger.error(
            'Could not %s %s with id %s, transition not allowed',
            logged_operation, entity_name, uuid_or_pk)
        six.reraise(StateChangeError, StateChangeError())

    logger.info(
        'Managed to %s %s with id %s',
        logged_operation, entity_name, uuid_or_pk
    )


def tracked_processing(model_class, processing_state, desired_state, error_state='set_erred'):
    def decorator(processing_fn):
        @functools.wraps(processing_fn)
        def wrapped(*args, **kwargs):
            # XXX: This is very fragile :(
            uuid_or_pk = args[0]

            set_entity_state = functools.partial(set_state, model_class, uuid_or_pk)

            try:
                set_entity_state(processing_state)

                # We should handle all exceptions here so that processing
                # can concentrate on positive flow

                # noinspection PyBroadException
                try:
                    processing_fn(*args, **kwargs)
                except Exception:
                    # noinspection PyProtectedMember
                    logger.exception(
                        'Failed to %s %s with id %s',
                        processing_state, model_class._meta.model_name, uuid_or_pk
                    )

                    set_entity_state(error_state)
                else:
                    set_entity_state(desired_state)
            except StateChangeError:
                # No logging is needed since set_state already logged everything
                pass

        return wrapped
    return decorator


class Throttle(object):
    """ Limit a number of celery tasks running in parallel.
        Retry task until conditions meet or timeout exceed.

        An instance can be used either as a decorator or as a context manager.

        .. code-block:: python
            @shared_task(name="change_instance")
            def change_instance1(instance_uuid):
                instance = Instance.objects.get(uuid=instance_uuid)
                with throttle(key=instance.cloud_project_membership.cloud.auth_url):
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
            @shared_task(name='nodeconductor.iaas.provision_instance')
            def provision_instance_fn(instance_uuid, backend_flavor_id)
                pass

        Call it by name:

        .. code-block:: python
            send_task('iaas', 'provision_instance')(instance_uuid, backend_flavor_id)

        Which is identical to:

        .. code-block:: python
            provision_instance_fn.delay(instance_uuid, backend_flavor_id)

    """

    def delay(*args, **kwargs):
        full_task_name = 'nodeconductor.%s.%s' % (app_label, task_name)
        send_celery_task(full_task_name, args, kwargs, countdown=2)

    return delay
