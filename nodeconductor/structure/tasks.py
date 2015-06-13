from __future__ import unicode_literals

import logging

from celery import shared_task

from nodeconductor.core.tasks import transition, retry_if_false
from nodeconductor.core.models import SshPublicKey, SynchronizationStates
from nodeconductor.core.log import EventLoggerAdapter
from nodeconductor.iaas.backend import ServiceBackendError, CloudBackendError
from nodeconductor.monitoring.zabbix.api_client import ZabbixApiClient
from nodeconductor.structure.handlers import PUSH_KEY, REMOVE_KEY
from nodeconductor.structure import models

logger = logging.getLogger(__name__)
event_logger = EventLoggerAdapter(logger)


@shared_task(name='nodeconductor.structure.sync_billing_customers')
def sync_billing_customers(customer_uuids=None):
    if not isinstance(customer_uuids, (list, tuple)):
        customer_uuids = models.Customer.objects.all().values_list('uuid', flat=True)

    map(sync_billing_customer.delay, customer_uuids)


@shared_task(name='nodeconductor.structure.sync_ssh_public_keys')
def sync_ssh_public_keys(action, ssh_public_keys_uuids, service_project_links):
    actions = {
        PUSH_KEY: push_ssh_public_key,
        REMOVE_KEY: remove_ssh_public_key,
    }

    try:
        task = actions[action]
    except KeyError:
        raise NotImplementedError("Action %s isn't supported by sync_ssh_public_keys" % action)

    for spl in service_project_links:
        for ssh_public_keys_uuid in ssh_public_keys_uuids:
            task.delay(ssh_public_keys_uuid, spl)


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
    backend = settings.get_backend()
    backend.sync()


@shared_task
@transition(models.ServiceSettings, 'set_in_sync')
def sync_service_settings_succeeded(settings_uuid, transition_entity=None):
    pass


@shared_task
@transition(models.ServiceSettings, 'set_erred')
def sync_service_settings_failed(settings_uuid, transition_entity=None):
    pass


@shared_task(max_retries=120, default_retry_delay=30)
@retry_if_false
def push_ssh_public_key(ssh_public_keys_uuid, service_project_link_str):
    try:
        public_key = SshPublicKey.objects.get(uuid=ssh_public_keys_uuid)
        service_project_link = next(models.ServiceProjectLink.from_string(service_project_link_str))
    except SshPublicKey.DoesNotExist:
        logging.warn('Missing public key %s.', ssh_public_keys_uuid)
        return True

    if service_project_link.state != SynchronizationStates.IN_SYNC:
        logging.warn(
            'Not pushing public keys for service project link %s which is in state %s.',
            service_project_link.pk, service_project_link.get_state_display())

        if service_project_link.state != SynchronizationStates.ERRED:
            logging.debug(
                'Rescheduling synchronisation of keys for link %s in state %s.',
                service_project_link.pk, service_project_link.get_state_display())

            # retry a task if service project link is in a sane state
            return False

    backend = service_project_link.get_backend()
    try:
        backend.add_ssh_key(public_key, service_project_link)
    except NotImplementedError:
        pass
    except (ServiceBackendError, CloudBackendError):
        logger.warn(
            'Failed to push public key %s for service project link %s',
            public_key.uuid, service_project_link.pk,
            exc_info=1)

        from nodeconductor.iaas.models import CloudProjectMembership

        if isinstance(service_project_link, CloudProjectMembership):
            # TODO: Refactor it according to NC-498
            event_logger.warning(
                'Failed to push public key %s to cloud membership %s.',
                public_key.uuid, service_project_link.pk,
                extra={
                    'project': service_project_link.project,
                    'cloud': service_project_link.cloud,
                    'event_type': 'sync_cloud_membership'}
            )

    return True


@shared_task(max_retries=120, default_retry_delay=30)
@retry_if_false
def remove_ssh_public_key(ssh_public_keys_uuid, service_project_link_str):
    public_key = SshPublicKey.objects.get(uuid=ssh_public_keys_uuid)
    service_project_link = next(models.ServiceProjectLink.from_string(service_project_link_str))

    backend = service_project_link.get_backend()
    backend.remove_ssh_key(public_key, service_project_link)
