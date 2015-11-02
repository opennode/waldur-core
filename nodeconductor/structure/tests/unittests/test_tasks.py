from django.test import TestCase

from nodeconductor.openstack.tests import factories as openstack_factories
from nodeconductor.structure import tasks as structure_tasks
from nodeconductor.structure.tests import factories as structure_factories
from nodeconductor.structure.utils import serialize_ssh_key, serialize_user


class TestTaskSkipsInvalidServiceProjectLink(TestCase):
    def setUp(self):
        link = openstack_factories.OpenStackServiceProjectLinkFactory()
        self.link_str = link.to_string()
        link.delete()

    def test_push_ssh_public_key(self):
        ssh_key = structure_factories.SshPublicKeyFactory()
        self.assertTrue(structure_tasks.push_ssh_public_key(ssh_key.uuid.hex, self.link_str))

    def test_remove_ssh_public_key(self):
        ssh_key = structure_factories.SshPublicKeyFactory()
        self.assertTrue(structure_tasks.remove_ssh_public_key(serialize_ssh_key(ssh_key), self.link_str))

    def test_add_user(self):
        user = structure_factories.UserFactory()
        self.assertTrue(structure_tasks.add_user(user.uuid.hex, self.link_str))

    def test_remove_user(self):
        user = structure_factories.UserFactory()
        self.assertTrue(structure_tasks.remove_user(serialize_user(user), self.link_str))
