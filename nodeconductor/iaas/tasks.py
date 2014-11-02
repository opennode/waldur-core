# coding: utf-8
from __future__ import absolute_import, unicode_literals

import logging

from celery import shared_task
from django.db import transaction

from nodeconductor.core.tasks import tracked_processing
from nodeconductor.core.log import EventLoggerAdapter
from nodeconductor.cloud import models as cloud_models
from nodeconductor.iaas import models

logger = logging.getLogger(__name__)
event_log = EventLoggerAdapter(logger)


class ResizingError(KeyError, models.Instance.DoesNotExist):
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


@shared_task
@tracked_processing(models.Instance, processing_state='begin_provisioning', desired_state='set_online')
def schedule_provisioning(instance_uuid):
    _mock_processing(instance_uuid)


@shared_task
@tracked_processing(models.Instance, processing_state='begin_stopping', desired_state='set_offline')
def schedule_stopping(instance_uuid, **kwargs):
    _mock_processing(instance_uuid)


@shared_task
@tracked_processing(models.Instance, processing_state='begin_starting', desired_state='set_online')
def schedule_starting(instance_uuid, **kwargs):
    _mock_processing(instance_uuid)


@shared_task
@tracked_processing(models.Instance, processing_state='begin_deleting', desired_state='set_deleted')
def schedule_deleting(instance_uuid, **kwargs):
    _mock_processing(instance_uuid)

@shared_task
@tracked_processing(models.Instance, processing_state='begin_resizing', desired_state='set_offline')
def schedule_resizing(instance_uuid, **kwargs):
    with transaction.atomic():
        instance = models.Instance.objects.get(uuid=instance_uuid)
        instance.flavor = cloud_models.Flavor.objects.get(uuid=kwargs['new_flavor'])
        instance.save()
