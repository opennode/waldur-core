import mock

from django.test import TestCase

from nodeconductor.openstack import tasks
from nodeconductor.openstack.backend import OpenStackBackendError
from nodeconductor.openstack.models import Instance
from nodeconductor.openstack.tests.factories import InstanceFactory


@mock.patch('nodeconductor.openstack.tasks.throttle')
@mock.patch('nodeconductor.structure.models.Service.get_backend')
class ErrorMessageTest(TestCase):

    def setUp(self):
        self.instance = InstanceFactory()
        self.error = OpenStackBackendError('Unable to find network')

    def test_if_instance_provision_fails_error_message_is_saved(self, mock_backend, mock_throttle):
        mock_backend().provision_instance.side_effect = self.error

        with self.assertRaises(OpenStackBackendError):
            tasks.provision_instance(self.instance.uuid.hex)

        self.assert_instance_has_error_message()

    def test_if_instance_start_fails_error_message_is_saved(self, mock_backend, mock_throttle):
        self.instance.state = Instance.States.STARTING_SCHEDULED
        self.instance.save()
        mock_backend()._old_backend.start_instance.side_effect = self.error

        with self.assertRaises(OpenStackBackendError):
            tasks.start_instance(self.instance.uuid.hex)

        self.assert_instance_has_error_message()

    def test_if_instance_stop_fails_error_message_is_saved(self, mock_backend, mock_throttle):
        self.instance.state = Instance.States.STOPPING_SCHEDULED
        self.instance.save()
        mock_backend()._old_backend.stop_instance.side_effect = self.error

        with self.assertRaises(OpenStackBackendError):
            tasks.stop_instance(self.instance.uuid.hex)

        self.assert_instance_has_error_message()

    def test_if_instance_restart_fails_error_message_is_saved(self, mock_backend, mock_throttle):
        self.instance.state = Instance.States.RESTARTING_SCHEDULED
        self.instance.save()
        mock_backend()._old_backend.restart_instance.side_effect = self.error

        with self.assertRaises(OpenStackBackendError):
            tasks.restart_instance(self.instance.uuid.hex)

        self.assert_instance_has_error_message()

    def test_if_instance_destroy_fails_error_message_is_saved(self, mock_backend, mock_throttle):
        self.instance.state = Instance.States.DELETION_SCHEDULED
        self.instance.save()
        mock_backend().delete_instance.side_effect = self.error

        with self.assertRaises(OpenStackBackendError):
            tasks.destroy_instance(self.instance.uuid.hex)

        self.assert_instance_has_error_message()

    def assert_instance_has_error_message(self):
        instance = Instance.objects.get(pk=self.instance.pk)
        self.assertEqual(instance.error_message, self.error.message)
