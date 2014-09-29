# coding: utf-8
from __future__ import absolute_import, unicode_literals

import logging

from celery import shared_task
from django_fsm import TransitionNotAllowed
from django.db import transaction

from nodeconductor.iaas import models

logger = logging.getLogger()


class BackgroundProcessingException(Exception):
    pass


def _mock_processing(should_fail=True):
    if should_fail:
        raise BackgroundProcessingException('It\'s not my day')

    import time
    time.sleep(10)


def _schedule_instance_operation(instance_uuid, operation, processing_callback):
    logger.info('About to %s instance with uuid %s' % (operation, instance_uuid))
    supported_operations = {
        'provisioning': ('provisioning', 'online'),
        'deleting': ('deleting', 'deleted'),
        'starting': ('starting', 'online'),
        'stopping': ('stopping', 'offline'),
    }

    with transaction.atomic():
        try:
            instance = models.Instance.objects.get(uuid=instance_uuid)
        except models.Instance.DoesNotExist:
            logger.error('Could not find instance with uuid %s to schedule %s for' % (instance_uuid, operation))
            # There's nothing we can do here to save the state of an instance
            return

        try:
            # mark start of the transition
            getattr(instance, supported_operations[operation][0])()
            instance.save()
        except TransitionNotAllowed:
            logger.warn('Transition from state %s using operation %s is not allowed'
                        % (instance.get_state_display(), operation))
            # Leave the instance intact
            return

    try:
        processing_callback()
    except BackgroundProcessingException as e:
        with transaction.atomic():
            try:
                instance = models.Instance.objects.get(uuid=instance_uuid)
            except models.Instance.DoesNotExist:
                logger.error('Could not find instance with uuid %s to mark as erred while running %s'
                             % (instance_uuid, operation))
                # There's nothing we can do here to save the state of an instance
                return

            logger.error('Error while performing instance %s operation %s: %s' % (instance_uuid, operation, e))
            instance.erred()
            instance.save()
            return

    # We need to get the fresh instance from db so that presentation layer
    # property changes would not get lost
    with transaction.atomic():
        try:
            instance = models.Instance.objects.get(uuid=instance_uuid)
        except models.Instance.DoesNotExist:
            logger.error('Instance with uuid %s has gone away during %s' % (instance_uuid, operation))

            # There's nothing we can do here to save the state of an instance
            return

        getattr(instance, supported_operations[operation][1])()
        instance.save()


@shared_task
def schedule_provisioning(instance_uuid):
    _schedule_instance_operation(instance_uuid, 'provisioning', _mock_processing)

@shared_task
def schedule_stopping(instance_uuid):
    _schedule_instance_operation(instance_uuid, 'stopping', _mock_processing)

@shared_task
def schedule_starting(instance_uuid):
    _schedule_instance_operation(instance_uuid, 'starting', _mock_processing)

@shared_task
def schedule_deleting(instance_uuid):
    _schedule_instance_operation(instance_uuid, 'deleting', _mock_processing)
