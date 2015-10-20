import logging

from celery import shared_task, chain

from nodeconductor.core.tasks import transition, retry_if_false
from nodeconductor.sugarcrm.backend import SugarCRMBackendError
from nodeconductor.sugarcrm.models import CRM


logger = logging.getLogger(__name__)


@shared_task(name='nodeconductor.sugarcrm.provision_crm')
def provision_crm(crm_uuid):
    chain(
        schedule_crm_instance_provision.si(crm_uuid),
        wait_for_crm_instance_state.si(crm_uuid, state='Online')
    ).apply_async(
        link=set_online.si(crm_uuid),
        link_error=set_erred.si(crm_uuid)
    )


@shared_task(name='nodeconductor.sugarcrm.stop_and_destroy_crm')
def stop_and_destroy_crm(crm_uuid):
    chain(
        schedule_crm_instance_stopping.si(crm_uuid),
        wait_for_crm_instance_state.si(crm_uuid, state='Offline'),
        set_offline.si(crm_uuid),
        schedule_deletion.si(crm_uuid),
        schedule_crm_instance_deletion.si(crm_uuid),
    ).apply_async(
        link=delete.si(crm_uuid),
        link_error=set_erred.si(crm_uuid),
    )


@shared_task
@transition(CRM, 'begin_provisioning')
def schedule_crm_instance_provision(crm_uuid, transition_entity=None):
    crm = transition_entity
    backend = crm.get_backend()
    backend.schedule_crm_instance_provision(crm)


@shared_task
@transition(CRM, 'begin_stopping')
def schedule_crm_instance_stopping(crm_uuid, transition_entity=None):
    crm = transition_entity
    backend = crm.get_backend()
    backend.schedule_crm_instance_stopping(crm)


@shared_task
@transition(CRM, 'begin_deleting')
def schedule_crm_instance_deletion(crm_uuid, transition_entity=None):
    crm = transition_entity
    backend = crm.get_backend()
    backend.schedule_crm_instance_deletion(crm)


@shared_task(max_retries=120, default_retry_delay=20)
@retry_if_false
def wait_for_crm_instance_state(crm_uuid, state, erred_state='Erred'):
    crm = CRM.objects.get(uuid=crm_uuid)
    backend = crm.get_backend()
    current_state = backend.get_crm_instance_state(crm)
    logger.info('Checking state for CRM "%s" (UUID: %s) instance. Current value: %s.',
                crm.name, crm.uuid.hex, current_state)
    if current_state == 'Erred':
        raise SugarCRMBackendError('CRM "%s" (UUID: %s) instance with UUID %s become erred. Check OpenStack app logs '
                                   'for more details.' % (crm.name, crm.uuid.hex, crm.backend_id))
    return current_state == state


@shared_task
@transition(CRM, 'set_online')
def set_online(crm_uuid, transition_entity=None):
    pass


@shared_task
@transition(CRM, 'set_offline')
def set_offline(crm_uuid, transition_entity=None):
    pass


@shared_task
@transition(CRM, 'schedule_deletion')
def schedule_deletion(crm_uuid, transition_entity=None):
    pass


@shared_task
@transition(CRM, 'set_erred')
def set_erred(crm_uuid, transition_entity=None):
    pass


@shared_task
def delete(crm_uuid):
    CRM.objects.get(uuid=crm_uuid).delete()
