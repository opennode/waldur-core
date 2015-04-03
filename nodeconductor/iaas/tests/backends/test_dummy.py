from django.test import TestCase

from nodeconductor.iaas.backend.openstack import OpenStackBackend
from nodeconductor.iaas.backend import CloudBackendError
from nodeconductor.iaas.models import OpenStackSettings


class OpenStackClientTest(TestCase):

    def setUp(self):
        settings, _ = OpenStackSettings.objects.update_or_create(
            auth_url='http://keystone.example.com:5000/v2.0',
            defaults={
                'username': 'test_user',
                'password': 'test_password',
                'tenant_name': 'test_tenant',
            }
        )
        self.credentials = {
            'auth_url': settings.auth_url,
            'username': settings.username,
            'password': settings.password,
            'tenant_id': '593af1f7b67b4d63b691fcabd2dad126',
        }
        self.backend = OpenStackBackend(dummy=True)

    def test_session(self):
        session = self.backend.create_tenant_session(self.credentials)
        self.assertEqual(session.auth.tenant_id, '593af1f7b67b4d63b691fcabd2dad126')

        session = self.backend.create_admin_session(self.credentials['auth_url'])
        self.assertIsNone(session.auth.tenant_id)

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

        self.assertIsNotNone(keystone.tenants.get(self.credentials['tenant_id']))
        with self.assertRaises(CloudBackendError):
            keystone.tenants.find(name='some_tenant')

        self.assertIsNotNone(keystone.tenants.create(tenant_name='some_tenant'))
        self.assertIsNotNone(keystone.tenants.find(name='some_tenant'))
        with self.assertRaises(CloudBackendError):
            keystone.tenants.create(tenant_name='test_tenant')

        user = keystone.users.create(name='joe_doe')
        role = keystone.roles.find(name='admin')
        tenant = keystone.tenants.find(name='test_tenant')

        user_role = keystone.roles.add_user_role(user=user.id, role=role.id, tenant=tenant.id)
        self.assertIs(user_role, role)

        with self.assertRaises(CloudBackendError):
            keystone.roles.add_user_role(user=user.id, role=role.id, tenant='xyz')

        with self.assertRaises(CloudBackendError):
            keystone.roles.add_user_role(user=user.id, role='xyz', tenant=tenant.id)
