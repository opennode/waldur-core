from __future__ import unicode_literals

import functools
import logging
import sys

from django.db import transaction, DatabaseError
from django.utils import six
from django_fsm import TransitionNotAllowed

from nodeconductor.core.log import EventLoggerAdapter

logger = logging.getLogger(__name__)
event_log = EventLoggerAdapter(logger)


class StateChangeError(RuntimeError):
    pass


# noinspection PyProtectedMember
def set_state(model_class, uuid, transition):
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
    :param uuid: identifier of the model_class instance
    :type uuid: str
    :param transition: name of model's method to trigger transition
    :type transition: str
    :raises: StateChangeError
    """
    logged_operation = transition.replace('_', ' ')
    entity_name = model_class._meta.model_name

    logger.info(
        'About to %s %s with uuid %s',
        logged_operation, entity_name, uuid
    )

    try:
        with transaction.atomic():
            entity = model_class._default_manager.get(uuid=uuid)

            # TODO: Make sure that the transition method actually exists
            transition = getattr(entity, transition)
            transition()

            entity.save()
    except model_class.DoesNotExist:
        msg = 'Could not %s %s with uuid %s. Instance has gone' %\
            (logged_operation, entity_name, uuid)
        # There's nothing we can do here to save the state of an entity
        logger.error(msg)

        six.reraise(StateChangeError, StateChangeError(msg), sys.exc_info()[2])
    except DatabaseError:
        # Transaction failed to commit, most likely due to concurrent update
        msg = 'Could not %s %s with uuid %s due to concurrent update' %\
              (logged_operation, entity_name, uuid)
        logger.error(msg)

        six.reraise(StateChangeError, StateChangeError(msg), sys.exc_info()[2])
    except TransitionNotAllowed:
        msg = 'Could not %s %s with uuid %s, transition not allowed' %\
              (logged_operation, entity_name, uuid)
        # Leave the entity intact
        logger.error(msg)
        six.reraise(StateChangeError, StateChangeError(msg), sys.exc_info()[2])

    logger.info(
        'Managed to %s %s with uuid %s',
        logged_operation, entity_name, uuid
    )
    event_log.info(
        'Finished to %s %s with uuid %s',
        logged_operation, entity_name, uuid
    )


def tracked_processing(model_class, processing_state, desired_state, error_state='set_erred'):
    def decorator(processing_fn):
        @functools.wraps(processing_fn)
        def wrapped(*args, **kwargs):
            # XXX: This is very fragile :(
            try:
                uuid = kwargs['uuid']
            except KeyError:
                uuid = args[0]

            set_entity_state = functools.partial(set_state, model_class, uuid)

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
                        'Failed to %s %s with uuid %s',
                        processing_state, model_class._meta.model_name, uuid
                    )

                    set_entity_state(error_state)
                else:
                    set_entity_state(desired_state)
            except StateChangeError:
                # No logging is needed since set_state already logged everything
                pass

        return wrapped
    return decorator
