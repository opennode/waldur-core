from ddt import data, ddt

from django.core.exceptions import ValidationError
from rest_framework import test

from nodeconductor.core import validators
from nodeconductor.structure.models import Customer


class NameValidationTest(test.APITransactionTestCase):
    def test_name_should_have_at_least_one_non_whitespace_character(self):
        with self.assertRaises(ValidationError):
            customer = Customer(name='      ')
            customer.full_clean()


@ddt
class MinCronValueValidatorTest(test.APITransactionTestCase):

    @data('*/1 * * * *', '*/10 * * * *', '*/59 * * * *')
    def test_validator_raises_validation_error_if_given_schedule_value_is_less_than_1_hours(self, value):
        validator = validators.MinCronValueValidator(limit_value=1)
        with self.assertRaises(ValidationError):
            validator(value)

    @data('hello world', '* * * * * *', '*/59')
    def test_validator_raises_validation_error_if_given_format_is_not_valid(self, value):
        validator = validators.MinCronValueValidator(limit_value=1)
        with self.assertRaises(ValidationError):
            validator(value)

    @data('0 * * * *', '0 0 * * *', '0 0 0 * *', '0 0 * * 0', '0 0 1 * *', '0 0 1 1 *', '0 0 1 1 *')
    def test_validator_does_not_raise_error_if_schedule_is_greater_than_or_equal_1_hour(self, value):
        validator = validators.MinCronValueValidator(limit_value=1)
        validator(value)
