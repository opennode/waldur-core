# coding: utf-8
from __future__ import absolute_import, unicode_literals

import functools
import logging
import sys

from celery import shared_task
from django_fsm import TransitionNotAllowed
from django.db import transaction, DatabaseError
import six

from nodeconductor.iaas import models

logger = logging.getLogger(__name__)


class StateChangeError(RuntimeError):
    pass


def _mock_processing(instance_uuid, should_fail=False):
    if should_fail:
        raise Exception('It\'s not my day')

    import time
    time.sleep(10)

    # update some values
    with transaction.atomic():
        try:
            instance = models.Instance.objects.get(uuid=instance_uuid)
            instance.ips = '1.2.3.4, 10.10.10.10'
            instance.save()
        except models.Instance.DoesNotExist:
            raise Exception('Error updating VM instance')


#TODO: extract to core
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
        from django.db import
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
        'About to start %s %s with uuid %s',
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
        msg = 'Could not perform %s %s with uuid, %s has gone' %\
            (logged_operation, entity_name, uuid, entity_name)
        # There's nothing we can do here to save the state of an entity
        logger.error(msg)

        six.reraise(StateChangeError, StateChangeError(msg), sys.exc_info()[2])
    except DatabaseError:
        # Transaction failed to commit, most likely due to concurrent update
        msg = 'Could not perform %s %s with uuid %s due to concurrent update' %\
              (logged_operation, entity_name, uuid)
        logger.error(msg)

        six.reraise(StateChangeError, StateChangeError(msg), sys.exc_info()[2])
    except TransitionNotAllowed:
        msg = 'Could not perform %s %s with uuid %s, transition not allowed' %\
              (logged_operation, entity.get_state_display(), uuid)
        # Leave the entity intact
        logger.error(msg)
        six.reraise(StateChangeError, StateChangeError(msg), sys.exc_info()[2])

    # TODO: Emit high level event log entry
    logger.info(
        'Managed to finish %s %s with uuid %s',
        logged_operation, entity_name, uuid
    )


def tracked_processing(model_class, processing_state, desired_state, error_state='erred'):
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
                        'Failed to finish %s %s with uuid %s',
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


@shared_task
@tracked_processing(models.Instance, processing_state='provisioning', desired_state='online')
def schedule_provisioning(instance_uuid):
    _mock_processing(instance_uuid)


@shared_task
@tracked_processing(models.Instance, processing_state='stopping', desired_state='offline')
def schedule_stopping(instance_uuid):
    _mock_processing(instance_uuid)


@shared_task
@tracked_processing(models.Instance, processing_state='starting', desired_state='online')
def schedule_starting(instance_uuid):
    _mock_processing(instance_uuid)


@shared_task
@tracked_processing(models.Instance, processing_state='deleting', desired_state='deleted')
def schedule_deleting(instance_uuid):
    _mock_processing(instance_uuid)
