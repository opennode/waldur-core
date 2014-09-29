# coding: utf-8
from __future__ import absolute_import, unicode_literals

import logging

from celery import shared_task
from django_fsm import TransitionNotAllowed
from django.db import transaction

from nodeconductor.iaas import models

logger = logging.getLogger()


@shared_task
def schedule_provisioning(instance_uuid):
    logger.info('About to provision instance with uuid %s', instance_uuid)

    with transaction.atomic():
        try:
            instance = models.Instance.objects.get(uuid=instance_uuid)
        except models.Instance.DoesNotExist:
            logger.error('Could not find instance with uuid %s to schedule provisioning for', instance_uuid)

            # There's nothing we can do here to save the state of an instance
            return

        try:
            instance.begin_provisioning()
            instance.save()
        except TransitionNotAllowed:
            logger.warn('ы?')
            # Leave the instance intact
            return

    # TODO: Lookup the backend implementation based on cloud
    # Delegate provisioning to backend
    import time
    time.sleep(10)

    # We need to get the fresh instance from db so that presentation layer
    # property changes would not get lost
    with transaction.atomic():
        try:
            instance = models.Instance.objects.get(uuid=instance_uuid)
        except models.Instance.DoesNotExist:
            logger.error('Instance with uuid %s has gone away during provisioning', instance_uuid)

            # There's nothing we can do here to save the state of an instance
            return

        instance.set_online()
        instance.save()
