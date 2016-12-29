from __future__ import unicode_literals

import logging

from celery import shared_task
from django.core import exceptions
from django.db import transaction
from django.utils import six, timezone

from nodeconductor.core import utils as core_utils, tasks as core_tasks
from nodeconductor.structure import SupportedServices, models, utils, ServiceBackendError


logger = logging.getLogger(__name__)


@shared_task(name='nodeconductor.structure.detect_vm_coordinates_batch')
def detect_vm_coordinates_batch(serialized_virtual_machines):
    for vm in serialized_virtual_machines:
        detect_vm_coordinates.delay(vm)


@shared_task(name='nodeconductor.structure.detect_vm_coordinates')
def detect_vm_coordinates(serialized_virtual_machine):

    try:
        vm = core_utils.deserialize_instance(serialized_virtual_machine)
    except exceptions.ObjectDoesNotExist:
        logger.warning('Missing virtual machine %s.', serialized_virtual_machine)
        return

    try:
        coordinates = vm.detect_coordinates()
    except utils.GeoIpException as e:
        logger.warning('Unable to detect coordinates for virtual machines %s: %s.', serialized_virtual_machine, e)
        return

    if coordinates:
        vm.latitude = coordinates.latitude
        vm.longitude = coordinates.longitude
        vm.save(update_fields=['latitude', 'longitude'])


@shared_task(name='nodeconductor.structure.check_expired_permissions')
def check_expired_permissions():
    for cls in models.BasePermission.get_all_models():
        for permission in cls.get_expired():
            permission.revoke()


class ConnectSharedSettingsTask(core_tasks.Task):

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


class BackgroundPullTask(core_tasks.BackgroundTask):
    """ Pull information about object from backend. Method "pull" should be implemented.

        Task marks object as ERRED if pull failed and recovers it if pull succeed.
    """

    def run(self, serialized_instance):
        instance = core_utils.deserialize_instance(serialized_instance)
        try:
            self.pull(instance)
        except ServiceBackendError as e:
            self.on_pull_fail(instance, e)
        else:
            self.on_pull_success(instance)

    def is_equal(self, other_task, serialized_instance):
        return self.name == other_task.get('name') and serialized_instance in other_task.get('args', [])

    def pull(self, instance):
        """ Pull instance from backend.

            This method should not handle backend exception.
        """
        raise NotImplementedError('Pull task should implement pull method.')

    def on_pull_fail(self, instance, error):
        error_message = six.text_type(error)
        self.log_error_message(instance, error_message)
        self.set_instance_erred(instance, error_message)

    def on_pull_success(self, instance):
        if instance.state == instance.States.ERRED:
            instance.recover()
            instance.error_message = ''
            instance.save(update_fields=['state', 'error_message'])

    def log_error_message(self, instance, error_message):
        logger_message = 'Failed to pull %s %s (PK: %s). Error: %s' % (
            instance.__class__.__name__, instance.name, instance.pk, error_message)
        if instance.state == instance.States.ERRED:  # report error on debug level if instance already was erred.
            logger.debug(logger_message)
        else:
            logger.error(logger_message, exc_info=True)

    def set_instance_erred(self, instance, error_message):
        """ Mark instance as erred and save error message """
        instance.set_erred()
        instance.error_message = error_message
        instance.save(update_fields=['state', 'error_message'])


class BackgroundListPullTask(core_tasks.BackgroundTask):
    """ Schedules pull task for each stable object of the model. """
    model = NotImplemented
    pull_task = NotImplemented

    def is_equal(self, other_task):
        return self.name == other_task.get('name')

    def get_pulled_objects(self):
        States = self.model.States
        return self.model.objects.filter(state__in=[States.ERRED, States.OK]).exclude(backend_id='')

    def run(self):
        for instance in self.get_pulled_objects():
            serialized = core_utils.serialize_instance(instance)
            self.pull_task().delay(serialized)


class ServiceSettingsBackgroundPullTask(BackgroundPullTask):

    def pull(self, service_settings):
        backend = service_settings.get_backend()
        backend.sync()


class ServiceSettingsListPullTask(BackgroundListPullTask):
    name = 'nodeconductor.structure.ServiceSettingsListPullTask'
    model = models.ServiceSettings
    pull_task = ServiceSettingsBackgroundPullTask

    def get_pulled_objects(self):
        States = self.model.States
        return self.model.objects.filter(state__in=[States.ERRED, States.OK])
