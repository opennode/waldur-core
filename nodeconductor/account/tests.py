from django.test import TestCase

from nodeconductor.server.test_settings import *
from nodeconductor.account.models import NodeUser

# Create your tests here.


class NodeUserTest(TestCase):
    def NodeUserCreationTest(self):
        """
        Creates a user with name, email and password set.
        """
        NodeUser.create_user('test', 'test@nodeconductor.com', 'asdf')
        self.assertTrue(NodeUser.objects.filter(name=="test").exists())


    def NodeUserCreationFailureTest(self):
        """
        Creates a user with email and password set, missing name.
        This is expected to fail.
        """
        NodeUser.create_user('', 'test@nodeconductor.com', 'asdf')
        self.assertFalse(NodeUser.objects.filter(email=="test@nodeconductor.com").exists())

    def NodeUserDeleteTest(self):
        NodeUser.create_user('test', 'test@nodeconductor.com', 'asdf')
        self.assertTrue(NodeUser.objects.filter(name=="test").exists())
        NodeUser.objects.get(name=="test").delete()
        self.assertFalse(NodeUser.objects.filter(name=="test").exists())
