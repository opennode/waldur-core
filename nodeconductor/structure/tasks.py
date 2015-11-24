from __future__ import unicode_literals

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from celery import shared_task

from nodeconductor.core.tasks import transition, retry_if_false, save_error_message
from nodeconductor.core.models import SshPublicKey, SynchronizationStates
from nodeconductor.iaas.backend import CloudBackendError
from nodeconductor.structure.log import event_logger
from nodeconductor.structure import (SupportedServices, ServiceBackendError,
                                     ServiceBackendNotImplemented, models)
from nodeconductor.structure.utils import deserialize_ssh_key, deserialize_user


logger = logging.getLogger(__name__)


@shared_task(name='nodeconductor.structure.stop_customer_resources')
def stop_customer_resources(customer_uuid):
    if not settings.NODECONDUCTOR.get('SUSPEND_UNPAID_CUSTOMERS'):
        return

    customer = models.Customer.objects.get(uuid=customer_uuid)
    for model_name, model in SupportedServices.get_resource_models().items():
        # Shutdown active resources for debtors
        # TODO: Consider supporting another states (like 'STARTING')
        # TODO: Remove IaaS support (NC-645)
        if model_name == 'IaaS.Instance':
            resources = model.objects.filter(
                state=model.States.ONLINE,
                cloud_project_membership__cloud__customer=customer)
        else:
            resources = model.objects.filter(
                state=model.States.ONLINE,
                service_project_link__service__customer=customer)

        for resource in resources:
            try:
                backend = resource.get_backend()
                backend.stop()
            except NotImplementedError:
                continue


@shared_task(name='nodeconductor.structure.recover_erred_services')
def recover_erred_services(service_project_links=None):
    if service_project_links is not None:
        erred_spls = models.ServiceProjectLink.from_string(service_project_links)
    else:
        for service_type, service in SupportedServices.get_service_models().items():
            # TODO: Remove IaaS support (NC-645)
            is_iaas = service_type == SupportedServices.Types.IaaS

            query = Q(state=SynchronizationStates.ERRED)
            if is_iaas:
                query |= Q(cloud__state=SynchronizationStates.ERRED)
            else:
                query |= Q(service__settings__state=SynchronizationStates.ERRED)

            erred_spls = service['service_project_link'].objects.filter(query)

    for spl in erred_spls:
        recover_erred_service.delay(spl.to_string(), is_iaas=is_iaas)


@shared_task(name='nodeconductor.structure.sync_service_settings')
def sync_service_settings(settings_uuids=None):
    settings = models.ServiceSettings.objects.all()
    if settings_uuids:
        if not isinstance(settings_uuids, (list, tuple)):
            settings_uuids = [settings_uuids]
        settings = settings.filter(uuid__in=settings_uuids)
    else:
        settings = settings.filter(state=SynchronizationStates.IN_SYNC)

    for obj in settings:
        settings_uuid = obj.uuid.hex
        if obj.state == SynchronizationStates.IN_SYNC:
            obj.schedule_syncing()
            obj.save()

            begin_syncing_service_settings.apply_async(
                args=(settings_uuid,),
                link=sync_service_settings_succeeded.si(settings_uuid),
                link_error=sync_service_settings_failed.si(settings_uuid))
        elif obj.state == SynchronizationStates.CREATION_SCHEDULED:
            begin_creating_service_settings.apply_async(
                args=(settings_uuid,),
                link=sync_service_settings_succeeded.si(settings_uuid),
                link_error=sync_service_settings_failed.si(settings_uuid))
        else:
            logger.warning('Cannot sync service settings %s from state %s', obj.name, obj.state)


@shared_task(name='nodeconductor.structure.sync_service_project_links', max_retries=120, default_retry_delay=5)
@retry_if_false
def sync_service_project_links(service_project_links=None, quotas=None, initial=False):
    if service_project_links is not None:
        link_objects = models.ServiceProjectLink.from_string(service_project_links)
        # Ignore iaas cloud project membership because it does not support default sync flow
        link_objects = [lo for lo in link_objects if lo._meta.app_label != 'iaas']
    else:
        # Ignore iaas cloud project membership because it does not support default sync flow
        spl_models = [model for model in models.ServiceProjectLink.get_all_models() if model._meta.app_label != 'iaas']
        link_objects = sum(
            [list(model.objects.filter(state=SynchronizationStates.IN_SYNC)) for model in spl_models], [])

    if not link_objects:
        return True

    for obj in link_objects:
        service_project_link_str = obj.to_string()
        if initial:
            # Ignore SPLs with ERRED service settings
            if obj.service.settings.state == SynchronizationStates.ERRED:
                break
            # For newly created SPLs make sure their settings in stable state, retry otherwise
            if obj.service.settings.state != SynchronizationStates.IN_SYNC:
                return False

            if obj.state == SynchronizationStates.NEW:
                obj.schedule_creating()
                obj.save()
            elif obj.state != SynchronizationStates.CREATION_SCHEDULED:
                # Don't sync already created SPL during initial phase
                return True

            begin_syncing_service_project_links.apply_async(
                args=(service_project_link_str,),
                kwargs={'quotas': quotas, 'initial': True, 'transition_method': 'begin_creating'},
                link=sync_service_project_link_succeeded.si(service_project_link_str),
                link_error=sync_service_project_link_failed.si(service_project_link_str))

        elif obj.state == SynchronizationStates.IN_SYNC:
            obj.schedule_syncing()
            obj.save()

            begin_syncing_service_project_links.apply_async(
                args=(service_project_link_str,),
                kwargs={'quotas': quotas, 'initial': False},
                link=sync_service_project_link_succeeded.si(service_project_link_str),
                link_error=sync_service_project_link_failed.si(service_project_link_str))

        else:
            logger.warning('Cannot sync SPL %s from state %s', obj.id, obj.state)

    return True


@shared_task
@transition(models.ServiceSettings, 'begin_syncing')
@save_error_message
def begin_syncing_service_settings(settings_uuid, transition_entity=None):
    settings = transition_entity
    try:
        backend = settings.get_backend()
        backend.sync()
    except ServiceBackendNotImplemented:
        pass


@shared_task
@transition(models.ServiceSettings, 'begin_creating')
@save_error_message
def begin_creating_service_settings(settings_uuid, transition_entity=None):
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


@shared_task
def begin_syncing_service_project_links(service_project_link_str, quotas=None, initial=False,
                                        transition_entity=None, transition_method='begin_syncing'):
    spl_model, spl_pk = models.ServiceProjectLink.parse_model_string(service_project_link_str)

    @transition(spl_model, transition_method)
    @save_error_message
    def process(service_project_link_pk, quotas=None, transition_entity=None):
        service_project_link = transition_entity
        try:
            backend = service_project_link.get_backend()
            if quotas:
                backend.sync_quotas(service_project_link, quotas)
            else:
                backend.sync_link(service_project_link, is_initial=initial)
        except ServiceBackendNotImplemented:
            pass

    process(spl_pk, quotas=quotas)


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


@shared_task
def recover_erred_service(service_project_link_str, is_iaas=False):
    try:
        spl = next(models.ServiceProjectLink.from_string(service_project_link_str))
    except StopIteration:
        logger.warning('Missing service project link %s.', service_project_link_str)
        return

    settings = spl.cloud if is_iaas else spl.service.settings

    try:
        backend = spl.get_backend()
        if is_iaas:
            try:
                if spl.state == SynchronizationStates.ERRED:
                    backend.create_session(membership=spl, dummy=spl.cloud.dummy)
                if spl.cloud.state == SynchronizationStates.ERRED:
                    backend.create_session(keystone_url=spl.cloud.auth_url, dummy=spl.cloud.dummy)
            except CloudBackendError:
                is_active = False
            else:
                is_active = True
        else:
            is_active = backend.ping()
    except (ServiceBackendError, ServiceBackendNotImplemented):
        is_active = False

    if is_active:
        for entity in (spl, settings):
            if entity.state == SynchronizationStates.ERRED:
                entity.set_in_sync_from_erred()
                entity.save()
    else:
        logger.info('Failed to recover service settings %s.' % settings)


@shared_task(name='nodeconductor.structure.push_ssh_public_key', max_retries=120, default_retry_delay=30)
@retry_if_false
def push_ssh_public_key(ssh_public_key_uuid, service_project_link_str):
    try:
        public_key = SshPublicKey.objects.get(uuid=ssh_public_key_uuid)
    except SshPublicKey.DoesNotExist:
        logger.warning('Missing public key %s.', ssh_public_key_uuid)
        return True
    try:
        service_project_link = next(models.ServiceProjectLink.from_string(service_project_link_str))
    except StopIteration:
        logger.warning('Missing service project link %s.', service_project_link_str)
        return True

    if service_project_link.state != SynchronizationStates.IN_SYNC:
        logger.debug(
            'Not pushing public keys for service project link %s which is in state %s.',
            service_project_link_str, service_project_link.get_state_display())

        if service_project_link.state != SynchronizationStates.ERRED:
            logger.debug(
                'Rescheduling synchronisation of keys for link %s in state %s.',
                service_project_link_str, service_project_link.get_state_display())

            # retry a task if service project link is not in a sane state
            return False

    backend = service_project_link.get_backend()
    try:
        backend.add_ssh_key(public_key, service_project_link)
        logger.info(
            'SSH key %s has been pushed to service project link %s.',
            public_key.uuid, service_project_link_str)
    except ServiceBackendNotImplemented:
        pass
    except (ServiceBackendError, CloudBackendError):
        logger.warning(
            'Failed to push SSH key %s to service project link %s.',
            public_key.uuid, service_project_link_str,
            exc_info=1)

    return True


@shared_task(name='nodeconductor.structure.remove_ssh_public_key')
def remove_ssh_public_key(key_data, service_project_link_str):
    public_key = deserialize_ssh_key(key_data)
    try:
        service_project_link = next(models.ServiceProjectLink.from_string(service_project_link_str))
    except StopIteration:
        logger.warning('Missing service project link %s.', service_project_link_str)
        return True

    try:
        backend = service_project_link.get_backend()
        backend.remove_ssh_key(public_key, service_project_link)
        logger.info(
            'SSH key %s has been removed from service project link %s.',
            public_key.uuid, service_project_link_str)
    except ServiceBackendNotImplemented:
        pass
    except (ServiceBackendError, CloudBackendError):
        logger.warning(
            'Failed to remove SSH key %s from service project link %s.',
            public_key.uuid, service_project_link_str,
            exc_info=1)


@shared_task(name='nodeconductor.structure.add_user', max_retries=120, default_retry_delay=30)
@retry_if_false
def add_user(user_uuid, service_project_link_str):
    try:
        user = get_user_model().objects.get(uuid=user_uuid)
    except get_user_model().DoesNotExist:
        logger.warning('Missing user %s.', user_uuid)
        return True
    try:
        service_project_link = next(models.ServiceProjectLink.from_string(service_project_link_str))
    except StopIteration:
        logger.warning('Missing service project link %s.', service_project_link_str)
        return True

    if service_project_link.state != SynchronizationStates.IN_SYNC:
        logger.debug(
            'Not adding users for service project link %s which is in state %s.',
            service_project_link_str, service_project_link.get_state_display())

        if service_project_link.state != SynchronizationStates.ERRED:
            logger.debug(
                'Rescheduling synchronisation of users for link %s in state %s.',
                service_project_link_str, service_project_link.get_state_display())

            # retry a task if service project link is not in a sane state
            return False

    backend = service_project_link.get_backend()
    try:
        backend.add_user(user, service_project_link)
        logger.info(
            'User %s has been added to service project link %s.',
            user.uuid, service_project_link_str)
    except ServiceBackendNotImplemented:
        pass
    except (ServiceBackendError, CloudBackendError):
        logger.warning(
            'Failed to add user %s for service project link %s',
            user.uuid, service_project_link_str,
            exc_info=1)

    return True


@shared_task(name='nodeconductor.structure.remove_user')
def remove_user(user_data, service_project_link_str):
    user = deserialize_user(user_data)
    try:
        service_project_link = next(models.ServiceProjectLink.from_string(service_project_link_str))
    except StopIteration:
        logger.warning('Missing service project link %s.', service_project_link_str)
        return True

    try:
        backend = service_project_link.get_backend()
        backend.remove_user(user, service_project_link)
        logger.info(
            'User %s has been removed from service project link %s.',
            user.uuid, service_project_link_str)
    except ServiceBackendNotImplemented:
        pass
