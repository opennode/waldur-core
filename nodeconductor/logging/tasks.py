from celery import shared_task

from nodeconductor.logging.log import event_logger
from nodeconductor.logging.models import BaseHook


@shared_task(name='nodeconductor.logging.process_event')
def process_event(event):
    for hook in BaseHook.get_hooks():
        if check_event(event, hook):
            hook.process(event)


def check_event(event, hook):
    # Check that event matches with hook
    if event['type'] not in hook.event_types:
        return False
    for key, uuids in event_logger.get_permitted_objects_uuids(hook.user).items():
        if key in event['context'] and event['context'][key] in uuids:
            return True
    return False
