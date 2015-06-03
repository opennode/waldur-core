from celery import shared_task, chain

from django.utils import timezone

from nodeconductor.core.tasks import transition, retry_if_false
from nodeconductor.structure.models import ServiceSettings
from nodeconductor.oracle.models import Database
from nodeconductor.oracle.backend import OracleBackendError


@shared_task(name='nodeconductor.oracle.provision_database', is_heavy_task=True)
def provision_database(database_uuid, provision_params):
    chain(
        create_database.s(database_uuid, provision_params),
        wait_for_status.s("RUNNING"),
    ).apply_async(
        link=set_database_online.si(database_uuid),
        link_error=set_database_erred.si(database_uuid))


@shared_task(name='nodeconductor.oracle.start_database')
def start_database(database_uuid):
    chain(
        begin_database_starting.s(database_uuid),
        wait_for_status.s("RUNNING"),
    ).apply_async(
        link=set_database_online.si(database_uuid),
        link_error=set_database_erred.si(database_uuid))


@shared_task(name='nodeconductor.oracle.stop_database')
def stop_database(database_uuid):
    chain(
        begin_database_stopping.s(database_uuid),
        wait_for_status.s("STOPPED"),
    ).apply_async(
        link=set_offline.si(database_uuid),
        link_error=set_database_erred.si(database_uuid))


@shared_task(name='nodeconductor.oracle.restart_database')
def restart_database(database_uuid):
    chain(
        begin_database_stopping.s(database_uuid),
        wait_for_status.s("STOPPED"),
        begin_database_starting.s(database_uuid),
        wait_for_status.s("RUNNING"),
    ).apply_async(
        link=set_database_online.si(database_uuid),
        link_error=set_database_erred.si(database_uuid))


@shared_task(max_retries=120, default_retry_delay=30)
@retry_if_false
def wait_for_status(action, status):
    settings = ServiceSettings.objects.get(uuid=action['settings_uuid'])
    backend = settings.get_backend()
    resource = backend.manager.request(action['resource_uri'])

    if resource['resource_state']['state'] == "EXCEPTION":
        raise OracleBackendError("Action %s failed: %s" % (resource['uri'], resource['status']))

    return resource['status'] == status


@shared_task
@transition(Database, 'begin_provisioning')
def create_database(database_uuid, provision_params, transition_entity=None):
    database = transition_entity
    backend = database.get_backend()
    backend_database = backend.create_database(provision_params)

    database.backend_id = backend.manager._get_uuid(backend_database['uri'])
    database.start_time = timezone.now()
    database.save()

    return {
        'settings_uuid': database.service_project_link.service.settings.uuid.hex,
        'resource_uri': backend_database['uri']}


@shared_task
@transition(Database, 'begin_starting')
def begin_database_starting(database_uuid, transition_entity=None):
    database = transition_entity
    backend = database.get_backend()
    backend_database = backend.database_operation(database.backend_id, "STARTUP")
    return {
        'settings_uuid': database.service_project_link.service.settings.uuid.hex,
        'resource_uri': backend_database['uri']}


@shared_task
@transition(Database, 'begin_stopping')
def begin_database_stopping(database_uuid, transition_entity=None):
    database = transition_entity
    backend = database.get_backend()
    backend_database = backend.database_operation(database.backend_id, "SHUTDOWN")
    return {
        'settings_uuid': database.service_project_link.service.settings.uuid.hex,
        'resource_uri': backend_database['uri']}


@shared_task
@transition(Database, 'set_online')
def set_database_online(database_uuid, transition_entity=None):
    database = transition_entity
    database.start_time = timezone.now()
    database.save(update_fields=['start_time'])


@shared_task
@transition(Database, 'set_offline')
def set_offline(database_uuid, transition_entity=None):
    database = transition_entity
    database.start_time = None
    database.save(update_fields=['start_time'])


@shared_task
@transition(Database, 'set_erred')
def set_database_erred(database_uuid, transition_entity=None):
    pass
