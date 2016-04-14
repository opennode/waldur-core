import logging

from celery import shared_task
from datetime import datetime
from django.conf import settings

from nodeconductor.logging.loggers import alert_logger, event_logger
from nodeconductor.logging.models import BaseHook, Alert, AlertThresholdMixin


logger = logging.getLogger(__name__)


@shared_task(name='nodeconductor.logging.process_event')
def process_event(event):
    for hook in BaseHook.get_active_hooks():
        if check_event(event, hook):
            hook.process(event)


def check_event(event, hook):
    # Check that event matches with hook
    if event['type'] not in hook.all_event_types:
        return False
    for key, uuids in event_logger.get_permitted_objects_uuids(hook.user).items():
        if key in event['context'] and event['context'][key] in uuids:
            return True
    return False


@shared_task(name='nodeconductor.logging.close_alerts_without_scope')
def close_alerts_without_scope():
    for alert in Alert.objects.filter(closed__isnull=True).iterator():
        if alert.scope is None:
            logger.error('Alert without scope was not closed. Alert id: %s.', alert.id)
            alert.close()


@shared_task(name='nodeconductor.logging.alerts_cleanup')
def alerts_cleanup():
    timespan = settings.NODECONDUCTOR.get('CLOSED_ALERTS_LIFETIME')
    if timespan:
        Alert.objects.filter(is_closed=True, closed__lte=datetime.now() - timespan).delete()


@shared_task(name='nodeconductor.logging.check_threshold')
def check_threshold():
    for model in AlertThresholdMixin.get_all_models():
        for obj in model.objects.get_current_queryset().filter(threshold__isnull=False).iterator():
            if obj.is_over_threshold():
                alert_logger.threshold.warning(
                    'Threshold for {scope_name} is exceeded.',
                    scope=obj.scope,
                    alert_type='threshold_exceeded',
                    alert_context={
                        'object': obj
                    })
            else:
                alert_logger.threshold.close(
                    scope=obj.scope,
                    alert_type='threshold_exceeded')
