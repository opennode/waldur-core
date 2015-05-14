from __future__ import absolute_import

import os

from celery import Celery
from celery import signals
from django.conf import settings

from nodeconductor.core.middleware import set_current_user, get_current_user, reset_current_user

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nodeconductor.server.settings')  # XXX:

app = Celery('nodeconductor')

# Using a string here means the worker will not have to
# pickle the object when using Windows.
app.config_from_object('django.conf:settings')
# Forced autodiscover required for proper work of nodeconductor.core.tasks.send_task
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS, force=True)


class PriorityRouter(object):
    """ Run heavy tasks in a separate queue.
        One must supply is_heavy_task=True as a keyword argument to task decorator.
    """
    def route_for_task(self, task_name, *args, **kwargs):
        task = app.tasks.get(task_name)
        if getattr(task, 'is_heavy_task', False):
            return {'queue': 'heavy'}
        return None


# The following signal handler should be gone after NC-389 is implemented.
# The idea should stay the same:
#  * at the logging site event context is generated
#  * this context is then explicitly passed to the background task;
#  * special base class for background task must be created, it will
#    get the event context passed as task parameter, and bind it to thread local
@signals.before_task_publish.connect
def pass_event_context(sender=None, body=None, **kwargs):
    if body is None:
        return

    user = get_current_user()
    if user is None:
        return

    body['kwargs']['event_context'] = {
        'user_username': user.username,
        'user_uuid': user.uuid.hex,
        'user_native_name': user.native_name,
        'user_full_name': user.full_name,
    }


@signals.task_prerun.connect
def bind_current_user(sender=None, **kwargs):
    try:
        event_context = kwargs['kwargs'].pop('event_context')
    except KeyError:
        return

    # XXX: This is just a compatibility layer, drop after NC-389 is done
    # In contrast to what is prosed in NC-389, extraction of the event log
    # attributes is currently done in EventFormatter.
    # EventFormatter expects get_current_user() to return an object
    # that looks like User from django.contrib.auth.
    # FakeUser extracts the relevant user fields from the event context
    # (whose structure is modeled after the one suggested in NC-389)
    # and wraps them into an User-like object for EventFormatter to consume.
    import uuid

    class FakeUser(object):
        def __init__(self, event_context):
            for k, v in event_context.items():
                if not k.startswith('user_'):
                    continue

                k = k[5:]
                if k == 'uuid':
                    v = uuid.UUID(v)

                setattr(self, k, v)

        def is_anonymous(self):
            return False

    user = FakeUser(event_context)

    set_current_user(user)


@signals.task_postrun.connect
def unbind_current_user(sender=None, **kwargs):
    reset_current_user()
