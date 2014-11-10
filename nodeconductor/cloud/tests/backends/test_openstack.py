from django.utils import unittest
from keystoneclient import exceptions as keystone_exceptions
import mock

from nodeconductor.cloud.backend import CloudBackendError

from nodeconductor.cloud.backend.openstack import OpenStackBackend


class OpenStackBackendPublicApiTest(unittest.TestCase):
    def setUp(self):
        self.keystone_client = mock.Mock()
        self.nova_client = mock.Mock()
        self.cloud_account = mock.Mock()
        self.membership = mock.Mock()
        self.tenant = mock.Mock()

        # Mock low level non-AbstractCloudBackend api methods
        self.backend = OpenStackBackend()
        self.backend.get_credentials = mock.Mock(return_value={})
        self.backend.get_keystone_client = mock.Mock(return_value=self.keystone_client)
        self.backend.get_nova_client = mock.Mock(return_value=self.nova_client)
        self.backend.get_or_create_tenant = mock.Mock(return_value=self.tenant)
        self.backend.get_or_create_user = mock.Mock(return_value=('john', 'doe'))
        self.backend.ensure_user_is_tenant_admin = mock.Mock()

    def test_push_cloud_account_does_not_call_openstack_api(self):
        self.backend.push_cloud_account(self.cloud_account)

        self.assertFalse(self.backend.get_keystone_client.called, 'Keystone client should not have been created')
        self.assertFalse(self.backend.get_nova_client.called, 'Nova client should not have been created')

    def test_push_cloud_account_does_not_update_cloud_account(self):
        self.backend.push_cloud_account(self.cloud_account)

        self.assertFalse(self.cloud_account.save.called, 'Cloud account should not have been updated')

    def test_push_membership_synchronizes_user(self):
        self.backend.push_membership(self.membership)

        self.backend.get_or_create_user.assert_called_once_with(self.membership, self.keystone_client)

    def test_push_membership_synchronizes_tenant(self):
        self.backend.push_membership(self.membership)

        self.backend.get_or_create_tenant.assert_called_once_with(self.membership, self.keystone_client)

    def test_push_membership_synchronizes_users_role_in_tenant(self):
        self.backend.push_membership(self.membership)

        self.backend.get_or_create_user.ensure_user_is_tenant_admin('john', self.tenant, self.keystone_client)

    def test_push_membership_updates_membership_with_backend_data(self):
        self.backend.push_membership(self.membership)

        self.assertEquals(self.membership.username, 'john')
        self.assertEquals(self.membership.password, 'doe')
        self.assertEquals(self.membership.tenant_id, self.tenant.id)

        self.membership.save.assert_called_once_with()

    def test_push_membership_raises_on_openstack_api_error(self):
        self.backend.get_keystone_client.side_effect = keystone_exceptions.AuthorizationFailure
        with self.assertRaises(CloudBackendError):
            self.backend.push_membership(self.membership)


class OpenStackBackendHelperApiTest(unittest.TestCase):
    def setUp(self):
        self.keystone_client = mock.Mock()
        self.nova_client = mock.Mock()

        self.membership = mock.Mock()
        self.membership.project.uuid.hex = 'project_uuid'
        self.membership.project.name = 'project_name'
        self.membership.project.description = 'project_description'

        self.backend = OpenStackBackend()

    # get_or_create_tenant tests
    def test_get_or_create_tenant_creates_tenant_with_proper_arguments(self):
        created_tenant = object()

        self.keystone_client.tenants.create.return_value = created_tenant
        tenant = self.backend.get_or_create_tenant(self.membership, self.keystone_client)

        self.keystone_client.tenants.create.assert_called_once_with(
            tenant_name='project_uuid-project_name',
            description='project_description',
        )

        self.assertEquals(tenant, created_tenant, 'Created tenant not returned')

    def test_get_or_create_tenant_looks_up_existing_tenant_if_creation_fails_due_to_conflict(self):
        existing_tenant = object()

        self.keystone_client.tenants.create.side_effect = keystone_exceptions.Conflict
        self.keystone_client.tenants.find.return_value = existing_tenant

        tenant = self.backend.get_or_create_tenant(self.membership, self.keystone_client)

        self.keystone_client.tenants.find.assert_called_once_with(
            name='project_uuid-project_name',
        )

        self.assertEquals(tenant, existing_tenant, 'Looked up tenant not returned')

    def test_get_or_create_tenant_raises_if_both_creation_and_lookup_failed(self):
        self.keystone_client.tenants.create.side_effect = keystone_exceptions.Conflict
        self.keystone_client.tenants.find.side_effect = keystone_exceptions.NotFound

        with self.assertRaises(keystone_exceptions.ClientException):
            self.backend.get_or_create_tenant(self.membership, self.keystone_client)

    # get_or_create_user tests
    def test_get_or_create_user_creates_user_if_membership_was_never_synchronized_before(self):
        # This is a brand new membership that was never synchronized
        self.membership.username = ''

        username, password = self.backend.get_or_create_user(self.membership, self.keystone_client)

        self.assertEqual(self.keystone_client.users.create.call_count, 1,
                         'tenant.users.create() must be called exactly once')

        call_kwargs = self.keystone_client.users.create.call_args[1]
        call_username = call_kwargs.get('name')
        call_password = call_kwargs.get('password')

        # Check created username matches returned ones
        self.assertEqual(
            (call_username, call_password), (username, password),
            'Credentials used for account creation do not match the ones returned')

        self.assertTrue(
            username.endswith('-{0}'.format('project_name')),
            'Username should contain project name'
        )
        self.assertTrue(password, 'Password should not be empty')

    def test_get_or_create_user_returns_existing_credentials_if_they_are_valid(self):
        # This is a membership that was synchronized before
        self.membership.username = 'my_user'
        self.membership.password = 'my_pass'

        # Pretend we can log in using existing credentials
        self.backend.get_keystone_client = mock.Mock()

        username, password = self.backend.get_or_create_user(self.membership, self.keystone_client)

        self.assertFalse(self.keystone_client.called,
                         'Keystone must not be accessed')

        self.assertEqual(
            ('my_user', 'my_pass'), (username, password),
            'Credentials do not match the ones stored in membership')

    def test_get_or_create_user_creates_user_with_the_username_if_existing_credentials_are_invalid(self):
        # This is a membership that was synchronized before...
        self.membership.username = 'my_user-project_name'
        self.membership.password = 'my_pass'

        # ... but they became stale
        self.backend.get_keystone_client = mock.Mock(side_effect=keystone_exceptions.AuthorizationFailure)

        username, password = self.backend.get_or_create_user(self.membership, self.keystone_client)

        self.assertEqual(self.keystone_client.users.create.call_count, 1,
                         'tenant.users.create() must be called exactly once')

        call_kwargs = self.keystone_client.users.create.call_args[1]
        call_username = call_kwargs.get('name')
        call_password = call_kwargs.get('password')

        # Check created username matches returned ones
        self.assertEqual(
            call_username, 'my_user-project_name',
            'Existing username should have been used')

        self.assertEqual(
            (call_username, call_password), (username, password),
            'Credentials used for account creation do not match the ones returned')

        self.assertTrue(
            username.endswith('-{0}'.format('project_name')),
            'Username should contain project name'
        )
        self.assertTrue(password, 'Password should not be empty')
