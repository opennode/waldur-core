from __future__ import unicode_literals

import logging

from celery import shared_task
from django.contrib.auth import get_user_model
from django.db import transaction

from nodeconductor.core import utils as core_utils
from nodeconductor.core.tasks import retry_if_false, throttle, StateTransitionTask, ErrorMessageTask, Task
from nodeconductor.core.models import SshPublicKey
from nodeconductor.iaas.backend import CloudBackendError
from nodeconductor.structure import (SupportedServices, ServiceBackendError,
                                     ServiceBackendNotImplemented, models)
from nodeconductor.structure.utils import deserialize_ssh_key, deserialize_user, GeoIpException

logger = logging.getLogger(__name__)


@shared_task(name='nodeconductor.structure.push_ssh_public_keys')
def push_ssh_public_keys(service_project_links):
    link_objects = models.ServiceProjectLink.from_string(service_project_links)
    for link in link_objects:
        str_link = link.to_string()

        ssh_keys = SshPublicKey.objects.filter(user__groups__projectrole__project=link.project)
        if not ssh_keys.exists():
            logger.debug('There are no SSH public keys to push for link %s', str_link)
            continue

        for key in ssh_keys:
            push_ssh_public_key.delay(key.uuid.hex, str_link)


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


@shared_task(name='nodeconductor.structure.detect_vm_coordinates_batch')
def detect_vm_coordinates_batch(virtual_machines):
    for vm in models.Resource.from_string(virtual_machines):
        detect_vm_coordinates.delay(vm.to_string())


@shared_task(name='nodeconductor.structure.detect_vm_coordinates')
def detect_vm_coordinates(vm_str):
    try:
        vm = next(models.Resource.from_string(vm_str))
    except StopIteration:
        logger.warning('Missing virtual machine %s.', vm_str)
        return

    try:
        coordinates = vm.detect_coordinates()
    except GeoIpException as e:
        logger.warning('Unable to detect coordinates for virtual machines %s: %s.', vm_str, e)
        return

    if coordinates:
        vm.latitude = coordinates.latitude
        vm.longitude = coordinates.longitude
        vm.save(update_fields=['latitude', 'longitude'])


class ConnectSharedSettingsTask(Task):

    def execute(self, service_settings):
        logger.debug('About to connect service settings "%s" to all available customers' % service_settings.name)
        if not service_settings.shared:
            raise ValueError('It is impossible to connect not shared settings')
        service_model = SupportedServices.get_service_models()[service_settings.type]['service']

        with transaction.atomic():
            for customer in models.Customer.objects.all():
                defaults = {'name': service_settings.name, 'available_for_all': True}
                service, _ = service_model.objects.get_or_create(
                    customer=customer, settings=service_settings, defaults=defaults)

                service_project_link_model = service.projects.through
                for project in service.customer.projects.all():
                    service_project_link_model.objects.get_or_create(project=project, service=service)
        logger.info('Successfully connected service settings "%s" to all available customers' % service_settings.name)


# CeleryBeat tasks

@shared_task(name='nodeconductor.structure.pull_service_settings')
def pull_service_settings():
    for service_settings in models.ServiceSettings.objects.filter(state=models.ServiceSettings.States.OK):
        serialized = core_utils.serialize_instance(service_settings)
        sync_service_settings.delay(serialized)
    for service_settings in models.ServiceSettings.objects.filter(state=models.ServiceSettings.States.ERRED):
        serialized = core_utils.serialize_instance(service_settings)
        sync_service_settings.apply_async(
            args=(serialized,),
            link=StateTransitionTask().si(serialized, state_transition='recover'),
            link_error=ErrorMessageTask().s(serialized),
        )


# Small work around to use @throttle decorator. Ideally we need to come with
# solution how to use BackendMethodTask with @throttle.
@shared_task
@throttle(concurrency=2, key='service_settings_sync')
def sync_service_settings(serialized_service_settings):
    service_settings = core_utils.deserialize_instance(serialized_service_settings)
    backend = service_settings.get_backend()
    backend.sync()
