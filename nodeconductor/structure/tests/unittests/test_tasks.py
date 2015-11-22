import mock

from django.test import TestCase

from nodeconductor.core.models import SynchronizationStates
from nodeconductor.openstack import models as openstack_models
from nodeconductor.openstack.tests import factories as openstack_factories
from nodeconductor.structure import models as structure_models
from nodeconductor.structure import tasks as structure_tasks
from nodeconductor.structure import ServiceBackendError
from nodeconductor.structure.tests import factories as structure_factories
from nodeconductor.structure.utils import serialize_ssh_key, serialize_user


@mock.patch('nodeconductor.structure.models.ServiceProjectLink.get_backend')
class TestSshSynchronizationTask(TestCase):
    def setUp(self):
        self.link = openstack_factories.OpenStackServiceProjectLinkFactory(
            state=SynchronizationStates.IN_SYNC)
        self.link_str = self.link.to_string()
        self.ssh_key = structure_factories.SshPublicKeyFactory()

    def test_push_ssh_public_key_calls_backend(self, mock_backend):
        structure_tasks.push_ssh_public_key(self.ssh_key.uuid.hex, self.link_str)
        self.assertTrue(mock_backend().add_ssh_key.called)

    def test_push_ssh_public_key_skips_if_link_is_gone(self, mock_backend):
        self.link.delete()
        self.assertFalse(mock_backend().add_ssh_key.called)

    def test_remove_ssh_public_key_calls_backend(self, mock_backend):
        structure_tasks.remove_ssh_public_key(serialize_ssh_key(self.ssh_key), self.link_str)
        self.assertTrue(mock_backend().remove_ssh_key.called)

    def test_remove_ssh_public_key_skips_if_link_is_gone(self, mock_backend):
        self.link.delete()
        structure_tasks.remove_ssh_public_key(serialize_ssh_key(self.ssh_key), self.link_str)
        self.assertFalse(mock_backend().remove_ssh_key.called)


@mock.patch('nodeconductor.structure.models.ServiceProjectLink.get_backend')
class TestUserSynchronizationTask(TestCase):
    def setUp(self):
        self.link = openstack_factories.OpenStackServiceProjectLinkFactory(
            state=SynchronizationStates.IN_SYNC)
        self.link_str = self.link.to_string()
        self.user = structure_factories.UserFactory()

    def test_add_user_calls_backend(self, mock_backend):
        structure_tasks.add_user(self.user.uuid.hex, self.link_str)
        self.assertTrue(mock_backend().add_user.called)

    def test_add_user_skips_if_link_is_gone(self, mock_backend):
        self.link.delete()
        structure_tasks.add_user(self.user.uuid.hex, self.link_str)
        self.assertFalse(mock_backend().add_user.called)

    def test_remove_user_calls_backend(self, mock_backend):
        structure_tasks.remove_user(serialize_user(self.user), self.link_str)
        self.assertTrue(mock_backend().remove_user.called)

    def test_remove_user_skips_if_link_is_gone(self, mock_backend):
        self.link.delete()
        structure_tasks.remove_user(serialize_user(self.user), self.link_str)
        self.assertFalse(mock_backend().remove_user.called)


@mock.patch('nodeconductor.structure.models.ServiceSettings.get_backend')
@mock.patch('nodeconductor.structure.handlers.event_logger')
class TestServiceSynchronizationTask(TestCase):
    def setUp(self):
        self.link = openstack_factories.OpenStackServiceProjectLinkFactory(
            state=SynchronizationStates.IN_SYNC)
        self.settings = self.link.service.settings

        self.link.schedule_syncing()
        self.link.save()

        self.settings.schedule_syncing()
        self.settings.save()

        self.exception = ServiceBackendError("Unable to authenticate user")

    def get_link(self):
        return openstack_models.OpenStackServiceProjectLink.objects.get(pk=self.link.pk)

    def get_settings(self):
        return structure_models.ServiceSettings.objects.get(pk=self.settings.pk)

    def test_when_service_has_failed_event_is_emitted(self, mock_event_logger, mock_backend):
        with self.assertRaises(ServiceBackendError):
            mock_backend().sync.side_effect = self.exception
            structure_tasks.begin_syncing_service_settings(self.settings.uuid.hex)

        settings = self.get_settings()
        self.assertEqual(settings.state, SynchronizationStates.ERRED)
        self.assertEqual(settings.error_message, self.exception.message)

        mock_event_logger.service_settings.error.assert_called_once_with(
            'Service settings {service_settings_name} has failed to sync.',
            event_type='service_settings_sync_failed',
            event_context={
                'service_settings': self.settings,
                'error_message': self.exception.message
            }
        )

    def test_when_service_project_link_has_failed_event_is_emitted(self, mock_event_logger, mock_backend):
        with self.assertRaises(ServiceBackendError):
            mock_backend().sync_link.side_effect = self.exception
            structure_tasks.begin_syncing_service_project_links(self.link.to_string())

        link = self.get_link()
        self.assertEqual(link.state, SynchronizationStates.ERRED)
        self.assertEqual(link.error_message, self.exception.message)

        mock_event_logger.service_project_link.error.assert_called_once_with(
            'Synchronization of service project link has failed.',
            event_type='service_project_link_sync_failed',
            event_context={
                'service_project_link': self.link,
                'error_message': self.exception.message
            }
        )

    def test_when_service_is_recovered_event_is_emitted(self, mock_event_logger, mock_backend):
        self.link.set_erred()
        self.link.save()

        self.settings.set_erred()
        self.settings.save()

        mock_backend().ping.return_value = True
        structure_tasks.recover_erred_service(self.link.to_string())

        settings = self.get_settings()
        self.assertEqual(settings.state, SynchronizationStates.IN_SYNC)
        self.assertEqual(settings.error_message, '')

        link = self.get_link()
        self.assertEqual(link.state, SynchronizationStates.IN_SYNC)
        self.assertEqual(link.error_message, '')

        mock_event_logger.service_settings.info.assert_called_once_with(
            'Service settings {service_settings_name} has been recovered.',
            event_type='service_settings_recovered',
            event_context={'service_settings': self.settings}
        )

        mock_event_logger.service_project_link.info.assert_called_once_with(
            'Service project link has been recovered.',
            event_type='service_project_link_recovered',
            event_context={'service_project_link': self.link}
        )
