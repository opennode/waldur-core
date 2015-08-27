from django.core.management import call_command
from django.test import TestCase

from nodeconductor.structure.tests.factories import CustomerFactory


class CreateSampleDataTest(TestCase):
    def setUp(self):
        self.customer = CustomerFactory()

    def test_create_sample_billing_data_fails(self):
        call_command('createsamplebillingdata')
