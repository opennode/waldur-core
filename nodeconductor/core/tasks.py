from __future__ import unicode_literals

import functools
import logging

from django.db import transaction, IntegrityError, DatabaseError
from django.utils import six
from django_fsm import TransitionNotAllowed

from celery.task import current
from celery.exceptions import MaxRetriesExceededError


logger = logging.getLogger(__name__)


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


def retry_if_false(func):
    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        is_true = func(*args, **kwargs)
        if not is_true:
            try:
                current.retry()
            except MaxRetriesExceededError:
                raise RuntimeError('Task %s failed to retry' % current.name)

        return is_true
    return wrapped
