from celery import shared_task, current_app
from functools import wraps

from nodeconductor.openstack.backend import OpenStackClient
from nodeconductor.core.tasks import retry_if_false


def track_openstack_session(task_fn):
    @wraps(task_fn)
    def wrapped(tracked_session, *args, **kwargs):
        client = OpenStackClient(session=tracked_session)
        task_fn(client, *args, **kwargs)
        return client.session
    return wrapped


def save_error_message_from_task(func):
    @wraps(func)
    def wrapped(task_uuid, *args, **kwargs):
        func(*args, **kwargs)
        result = current_app.AsyncResult(task_uuid)
        transition_entity = kwargs['transition_entity']
        message = result.result['exc_message']
        if message:
            transition_entity.error_message = message
            transition_entity.save(update_fields=['error_message'])
    return wrapped


@shared_task
@track_openstack_session
def nova_server_resize(client, server_id, flavor_id):
    client.nova.servers.resize(server_id, flavor_id, 'MANUAL')


@shared_task
@track_openstack_session
def nova_server_resize_confirm(client, server_id):
    client.nova.servers.confirm_resize(server_id)


@shared_task(max_retries=300, default_retry_delay=3)
@track_openstack_session
@retry_if_false
def nova_wait_for_server_status(client, server_id, status):
    server = client.nova.servers.get(server_id)
    return server.status == status
