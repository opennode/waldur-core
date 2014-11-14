from django.core.exceptions import ValidationError
from django.utils import unittest

from nodeconductor.core import models as core_models
from nodeconductor.iaas.tests import factories as iaas_factories


class SshKeyValidatorTest(unittest.TestCase):
    def setUp(self):
        self.validate_key = core_models.validate_ssh_public_key
        self.public_key = iaas_factories.SshPublicKeyFactory.public_key

    def test_valid_ssh_key(self):
        try:
            self.validate_key(self.public_key)
        except ValidationError as error:
            self.fail('Valid public key validation has failed: %s' % error[0])

    def test_ssh_key_with_invalid_type_raises_validation_error(self):
        key_with_invalid_type = self.public_key.replace('ssh-rsa', 'ssh-dss')
        self.assertRaisesRegexp(ValidationError, 'Invalid SSH public key type ssh-dss, only ssh-rsa is supported',
                                self.validate_key, key_with_invalid_type)

    def test_ssh_key_with_invalid_body_raises_validation_error(self):
        key_body = self.public_key.split()[1]
        key_with_invalid_body = ' '.join(['ssh-rsa', key_body[:len(key_body) // 2], 'test'])
        self.assertRaisesRegexp(ValidationError, 'Invalid SSH public key body',
                                self.validate_key, key_with_invalid_body)

    def test_ssh_key_with_invalid_structure_raises_validation_error(self):
        key_with_invalid_structure = self.public_key.replace(' ', '')
        self.assertRaisesRegexp(ValidationError, 'Invalid SSH public key structure',
                                self.validate_key, key_with_invalid_structure)

    def test_ssh_key_with_invalid_encoded_type_within_body_raises_validation_error(self):
        key_body = self.public_key.split()[1]

        dss_encoded_type = 'AAAAB3NzaC1kc3MA'
        dss_key_body = key_body.replace(key_body[:len(dss_encoded_type)], dss_encoded_type)

        key_with_invalid_body = ' '.join(['ssh-rsa', dss_key_body, 'test'])

        self.assertRaisesRegexp(ValidationError, "Invalid encoded SSH public key type ssh-dss within the key's body, "
                                                 "only ssh-rsa is supported",
                                self.validate_key, key_with_invalid_body)
