from __future__ import unicode_literals

import logging

from celery import shared_task
from django.db import transaction

from nodeconductor.core import utils as core_utils
from nodeconductor.core.tasks import throttle, StateTransitionTask, ErrorMessageTask, Task
from nodeconductor.structure import SupportedServices, models, utils


logger = logging.getLogger(__name__)


@shared_task(name='nodeconductor.structure.detect_vm_coordinates_batch')
def detect_vm_coordinates_batch(virtual_machines):
    for vm in models.ResourceMixin.from_string(virtual_machines):
        detect_vm_coordinates.delay(vm.to_string())


@shared_task(name='nodeconductor.structure.detect_vm_coordinates')
def detect_vm_coordinates(vm_str):
    try:
        vm = next(models.ResourceMixin.from_string(vm_str))
    except StopIteration:
        logger.warning('Missing virtual machine %s.', vm_str)
        return

    try:
        coordinates = vm.detect_coordinates()
    except utils.GeoIpException as e:
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
            raise ValueError('It is impossible to connect non-shared settings')
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
@shared_task(is_background=True)
@throttle(concurrency=2, key='service_settings_sync')
def sync_service_settings(serialized_service_settings):
    service_settings = core_utils.deserialize_instance(serialized_service_settings)
    backend = service_settings.get_backend()
    backend.sync()
