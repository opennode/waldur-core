from django.test import TestCase

from nodeconductor.iaas.backend import CloudBackendError
from nodeconductor.iaas.backend.openstack import OpenStackBackend


class OpenStackClientTest(TestCase):

    def setUp(self):
        self.credentials = {
            'auth_url': 'http://keystone.example.com:5000/v2.0',
            'username': 'test_user',
            'password': 'test_password',
            'tenant_name': 'test_tenant',
        }
        self.backend = OpenStackBackend(dummy=True)

    def test_session(self):
        session = self.backend.create_tenant_session(self.credentials)
        self.assertEqual(session['tenant_id'], '593af1f7b67b4d63b691fcabd2dad126')

        with self.assertRaisesRegexp(CloudBackendError, "Authentication failure"):
            crdts = self.credentials.copy()
            crdts['password'] = 'noclue'
            self.backend.create_tenant_session(crdts)

        with self.assertRaises(CloudBackendError):
            crdts = self.credentials.copy()
            crdts['auth_url'] = 'another.example.com'
            self.backend.create_tenant_session(crdts)

        sess1 = dict(session.copy())
        sess2 = OpenStackBackend.recover_session(sess1)
        self.assertTrue(sess2.dummy)

    def test_keystone(self):
        session = self.backend.create_tenant_session(self.credentials)
        keystone = self.backend.create_keystone_client(session)

        self.assertIsNotNone(keystone.tenants.find(name=self.credentials['tenant_name']))
        with self.assertRaises(CloudBackendError):
            keystone.tenants.find(name='some_tenant')

        self.assertIsNotNone(keystone.tenants.create(tenant_name='some_tenant'))
        with self.assertRaises(CloudBackendError):
            keystone.tenants.create(tenant_name=self.credentials['tenant_name'])
