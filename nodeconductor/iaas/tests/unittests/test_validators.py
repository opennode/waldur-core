from django.core.exceptions import ValidationError
from django.utils import unittest

from nodeconductor.core.models import validate_ssh_public_key


class SshKeyValidatorTest(unittest.TestCase):
    def test_valid_ssh_key(self):
        valid_key = (
        "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDDURXDP5YhOQUYoDuTxJ84DuzqMJYJqJ8+SZT28"
        "TtLm5yBDRLKAERqtlbH2gkrQ3US58gd2r8H9jAmQOydfvgwauxuJUE4eDpaMWupqquMYsYLB5f+vVGhdZbbzfc6DTQ2rY"
        "dknWoMoArlG7MvRMA/xQ0ye1muTv+mYMipnd7Z+WH0uVArYI9QBpqC/gpZRRIouQ4VIQIVWGoT6M4Kat5ZBXEa9yP+9du"
        "D2C05GX3gumoSAVyAcDHn/xgej9pYRXGha4l+LKkFdGwAoXdV1z79EG1+9ns7wXuqMJFHM2KDpxAizV0GkZcojISvDwuh"
        "vEAFdOJcqjyyH4FOGYa8usP1 test"
        )
        validate_ssh_public_key(valid_key)

    def test_ssh_key_with_invalid_type_raises_validation_error(self):
        key_with_invalid_type = "ssh-dsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDDU test"

        with self.assertRaisesRegexp(ValidationError,
                                     'Invalid SSH public key type ssh-dsa, only ssh-rsa is supported'):
            validate_ssh_public_key(key_with_invalid_type)

    def test_ssh_key_with_invalid_body_raises_validation_error(self):
        key_with_invalid_body = "ssh-rsa invalid_body test"

        with self.assertRaisesRegexp(ValidationError, 'Invalid SSH public key body'):
            validate_ssh_public_key(key_with_invalid_body)

    def test_ssh_key_with_invalid_structure_raises_validation_error(self):
        key_with_invalid_structure = "ssh-dsaAAAB3NzaC1yc2EAAAADtest"

        with self.assertRaisesRegexp(ValidationError, 'Invalid SSH public key structure'):
            validate_ssh_public_key(key_with_invalid_structure)

    def test_ssh_key_with_invalid_encoded_type_within_body_raises_validation_error(self):
        key_with_invalid_body = "ssh-rsa AAAAB3NzaC1kc3MA"

        with self.assertRaisesRegexp(ValidationError,
                                     "Invalid encoded SSH public key type ssh-dss within the key's body, "
                                     "only ssh-rsa is supported"):
            validate_ssh_public_key(key_with_invalid_body)
