import mock

from django.test import TestCase

from nodeconductor.openstack.tests import factories as openstack_factories
from nodeconductor.structure import tasks as structure_tasks
from nodeconductor.structure.tests import factories as structure_factories
from nodeconductor.structure.utils import serialize_ssh_key, serialize_user


@mock.patch('nodeconductor.structure.models.ServiceProjectLink.get_backend')
class TestSshSynchronizationTask(TestCase):
    def setUp(self):
        self.link = openstack_factories.OpenStackServiceProjectLinkFactory()
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
        self.link = openstack_factories.OpenStackServiceProjectLinkFactory()
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
