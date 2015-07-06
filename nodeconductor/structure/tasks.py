from __future__ import unicode_literals

import logging

from celery import shared_task
from django.contrib.auth import get_user_model

from nodeconductor.core.tasks import transition, retry_if_false
from nodeconductor.core.models import SshPublicKey, SynchronizationStates
from nodeconductor.iaas.backend import CloudBackendError
from nodeconductor.monitoring.zabbix.api_client import ZabbixApiClient
from nodeconductor.structure import ServiceBackendError, ServiceBackendNotImplemented, models, handlers

logger = logging.getLogger(__name__)


@shared_task(name='nodeconductor.structure.sync_billing_customers')
def sync_billing_customers(customer_uuids=None):
    if not isinstance(customer_uuids, (list, tuple)):
        customer_uuids = models.Customer.objects.all().values_list('uuid', flat=True)

    map(sync_billing_customer.delay, customer_uuids)


@shared_task(name='nodeconductor.structure.sync_users')
def sync_users(action, entities_uuids, service_project_links):
    actions = {
        handlers.PUSH_KEY: push_ssh_public_key,
        handlers.REMOVE_KEY: remove_ssh_public_key,
        handlers.ADD_USER: add_user,
        handlers.REMOVE_USER: remove_user,
    }

    try:
        task = actions[action]
    except KeyError:
        raise NotImplementedError("Action %s isn't supported by sync_users" % action)

    for spl in service_project_links:
        for entity_uuid in entities_uuids:
            task.delay(entity_uuid, spl)


@shared_task
def create_zabbix_hostgroup(project_uuid):
    project = models.Project.objects.get(uuid=project_uuid)
    zabbix_client = ZabbixApiClient()
    zabbix_client.create_hostgroup(project)


@shared_task
def delete_zabbix_hostgroup(project_uuid):
    project = models.Project.objects.get(uuid=project_uuid)
    zabbix_client = ZabbixApiClient()
    zabbix_client.delete_hostgroup(project)


@shared_task
def sync_billing_customer(customer_uuid):
    customer = models.Customer.objects.get(uuid=customer_uuid)
    backend = customer.get_billing_backend()
    backend.sync_customer()
    backend.sync_invoices()


@shared_task(name='nodeconductor.structure.sync_service_settings')
def sync_service_settings(settings_uuids=None, initial=False):
    settings = models.ServiceSettings.objects.all()
    if settings_uuids:
        if not isinstance(settings_uuids, (list, tuple)):
            settings_uuids = [settings_uuids]
        settings = settings.filter(uuid__in=settings_uuids)
    else:
        settings = settings.filter(state=SynchronizationStates.IN_SYNC)

    for obj in settings:
        # Settings are being created in SYNCING_SCHEDULED state,
        # thus bypass transition during 'initial' sync.
        if not initial:
            obj.schedule_syncing()
            obj.save()

        settings_uuid = obj.uuid.hex
        begin_syncing_service_settings.apply_async(
            args=(settings_uuid,),
            link=sync_service_settings_succeeded.si(settings_uuid),
            link_error=sync_service_settings_failed.si(settings_uuid))


@shared_task
@transition(models.ServiceSettings, 'begin_syncing')
def begin_syncing_service_settings(settings_uuid, transition_entity=None):
    settings = transition_entity
    try:
        backend = settings.get_backend()
        backend.sync()
    except ServiceBackendNotImplemented:
        pass


@shared_task
@transition(models.ServiceSettings, 'set_in_sync')
def sync_service_settings_succeeded(settings_uuid, transition_entity=None):
    pass


@shared_task
@transition(models.ServiceSettings, 'set_erred')
def sync_service_settings_failed(settings_uuid, transition_entity=None):
    pass


@shared_task(name='nodeconductor.structure.sync_service_project_links')
def sync_service_project_links(service_project_links=None, initial=False):
    if service_project_links and not isinstance(service_project_links, (list, tuple)):
        service_project_links = [service_project_links]

    for obj in models.ServiceProjectLink.from_string(service_project_links):
        # Settings are being created in SYNCING_SCHEDULED state,
        # thus bypass transition during 'initial' sync.
        if not initial:
            obj.schedule_syncing()
            obj.save()

        service_project_link_str = obj.to_string()
        begin_syncing_service_project_links.apply_async(
            args=(service_project_link_str,),
            link=sync_service_project_link_succeeded.si(service_project_link_str),
            link_error=sync_service_project_link_failed.si(service_project_link_str))


@shared_task
def begin_syncing_service_project_links(service_project_link_str, transition_entity=None):
    spl_model, spl_pk = models.ServiceProjectLink.parse_model_string(service_project_link_str)

    @transition(spl_model, 'begin_syncing')
    def process(service_project_link_pk, transition_entity=None):
        service_project_link = transition_entity
        try:
            # Get administrative backend session from service instead of tenant session from spl
            backend = service_project_link.service.get_backend()
            backend.sync_membership(service_project_link)
        except ServiceBackendNotImplemented:
            pass

    process(spl_pk)


@shared_task
def sync_service_project_link_succeeded(service_project_link_str):
    spl_model, spl_pk = models.ServiceProjectLink.parse_model_string(service_project_link_str)

    @transition(spl_model, 'set_in_sync')
    def process(service_project_link_pk, transition_entity=None):
        pass

    process(spl_pk)


@shared_task
def sync_service_project_link_failed(service_project_link_str):
    spl_model, spl_pk = models.ServiceProjectLink.parse_model_string(service_project_link_str)

    @transition(spl_model, 'set_erred')
    def process(service_project_link_pk, transition_entity=None):
        pass

    process(spl_pk)


@shared_task(max_retries=120, default_retry_delay=30)
@retry_if_false
def push_ssh_public_key(ssh_public_key_uuid, service_project_link_str):
    try:
        public_key = SshPublicKey.objects.get(uuid=ssh_public_key_uuid)
        service_project_link = next(models.ServiceProjectLink.from_string(service_project_link_str))
    except SshPublicKey.DoesNotExist:
        logging.warn('Missing public key %s.', ssh_public_key_uuid)
        return True

    if service_project_link.state != SynchronizationStates.IN_SYNC:
        logging.warn(
            'Not pushing public keys for service project link %s which is in state %s.',
            service_project_link_str, service_project_link.get_state_display())

        if service_project_link.state != SynchronizationStates.ERRED:
            logging.debug(
                'Rescheduling synchronisation of keys for link %s in state %s.',
                service_project_link_str, service_project_link.get_state_display())

            # retry a task if service project link is in a sane state
            return False

    backend = service_project_link.get_backend()
    try:
        backend.add_ssh_key(public_key, service_project_link)
    except ServiceBackendNotImplemented:
        pass
    except (ServiceBackendError, CloudBackendError):
        logger.warn(
            'Failed to push public key %s for service project link %s',
            public_key.uuid, service_project_link_str,
            exc_info=1)
    return True


@shared_task()
def remove_ssh_public_key(ssh_public_key_uuid, service_project_link_str):
    public_key = SshPublicKey.objects.get(uuid=ssh_public_key_uuid)
    service_project_link = next(models.ServiceProjectLink.from_string(service_project_link_str))

    try:
        backend = service_project_link.get_backend()
        backend.remove_ssh_key(public_key, service_project_link)
    except ServiceBackendNotImplemented:
        pass


@shared_task(max_retries=120, default_retry_delay=30)
@retry_if_false
def add_user(user_uuid, service_project_link_str):
    user = get_user_model().objects.get(uuid=user_uuid)
    service_project_link = next(models.ServiceProjectLink.from_string(service_project_link_str))

    if service_project_link.state != SynchronizationStates.IN_SYNC:
        logging.warn(
            'Not adding users for service project link %s which is in state %s.',
            service_project_link_str, service_project_link.get_state_display())

        if service_project_link.state != SynchronizationStates.ERRED:
            logging.debug(
                'Rescheduling synchronisation of users for link %s in state %s.',
                service_project_link_str, service_project_link.get_state_display())

            # retry a task if service project link is in a sane state
            return False

    backend = service_project_link.get_backend()
    try:
        backend.add_user(user, service_project_link)
    except ServiceBackendNotImplemented:
        pass
    except (ServiceBackendError, CloudBackendError):
        logger.warn(
            'Failed to add user %s for service project link %s',
            user.uuid, service_project_link_str,
            exc_info=1)
    return True


@shared_task()
def remove_user(user_uuid, service_project_link_str):
    user = get_user_model().objects.get(uuid=user_uuid)
    service_project_link = next(models.ServiceProjectLink.from_string(service_project_link_str))

    try:
        backend = service_project_link.get_backend()
        backend.remove_user(user, service_project_link)
    except ServiceBackendNotImplemented:
        pass
