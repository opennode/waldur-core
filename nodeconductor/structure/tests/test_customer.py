from __future__ import unicode_literals

from unittest import TestCase

from nodeconductor.structure.models import CustomerRole
from nodeconductor.structure.tests import factories


class CustomerRoleTest(TestCase):
    def setUp(self):
        self.customer = factories.CustomerFactory()

    def test_owner_customer_role_is_created_upon_customer_creation(self):
        self.assertTrue(self.customer.roles.filter(role_type=CustomerRole.OWNER).exists(),
                        'Owner role should have been created')
