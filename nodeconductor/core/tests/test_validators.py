from django.core.exceptions import ValidationError
from rest_framework import test

from nodeconductor.structure.models import Customer


class NameValidationTest(test.APITransactionTestCase):
    def test_name_should_have_at_least_one_non_whitespace_character(self):
        with self.assertRaises(ValidationError):
            customer = Customer(name='      ')
            customer.full_clean()
