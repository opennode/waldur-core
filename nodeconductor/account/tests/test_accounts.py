from django.test import TestCase

from django.conf import settings
from nodeconductor.account.models import NodeUser


class NodeUserTest(TestCase):
    def test_node_user_successful_creation(self):
        """
        Creates a user with name, email and password set.
        """
        NodeUser.objects.create_user('test', 'test@nodeconductor.com', 'asdf')
        self.assertTrue(NodeUser.objects.filter(username="test").exists())


    def test_node_user_missing_inputs(self):
        """
        Creates a user with email and password set, missing username.
        This is expected to fail.
        """
        with self.assertRaises(ValueError):
                NodeUser.objects.create_user('', 'test@nodeconductor.com', 'asdf')

    def test_node_user_delete(self):
        NodeUser.objects.create_user('test', 'test@nodeconductor.com', 'asdf')
        self.assertTrue(NodeUser.objects.filter(username="test").exists())
        NodeUser.objects.get(username="test").delete()
        self.assertFalse(NodeUser.objects.filter(username="test").exists())
