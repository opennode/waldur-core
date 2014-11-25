from __future__ import unicode_literals

import collections

from django.test import TransactionTestCase
from django.utils import unittest
from keystoneclient import exceptions as keystone_exceptions
import mock

from nodeconductor.cloud.backend import CloudBackendError
from nodeconductor.cloud.backend.openstack import OpenStackBackend
from nodeconductor.cloud.models import Flavor
from nodeconductor.cloud.tests import factories
from nodeconductor.iaas.models import Image
from nodeconductor.iaas.tests import factories as iaas_factories

NovaFlavor = collections.namedtuple('NovaFlavor',
                                    ['id', 'name', 'vcpus', 'ram', 'disk'])

GlanceImage = collections.namedtuple(
    'GlanceImage',
    ['id', 'is_public', 'deleted']
)


def next_unique_flavor_id():
    return factories.FlavorFactory.build().flavor_id


def nc_flavor_to_nova_flavor(flavor):
    return NovaFlavor(
        id=flavor.flavor_id,
        name=flavor.name,
        vcpus=flavor.cores,
        ram=flavor.ram / 1024,
        disk=flavor.disk / 1024,
    )


class OpenStackBackendPublicApiTest(unittest.TestCase):
    def setUp(self):
        self.keystone_client = mock.Mock()
        self.nova_client = mock.Mock()
        self.neutron_client = mock.Mock()
        self.cloud_account = mock.Mock()
        self.membership = mock.Mock()
        self.tenant = mock.Mock()

        # Mock low level non-AbstractCloudBackend api methods
        self.backend = OpenStackBackend()
        self.backend.create_admin_session = mock.Mock()
        self.backend.create_user_session = mock.Mock()
        self.backend.create_keystone_client = mock.Mock(return_value=self.keystone_client)
        self.backend.create_nova_client = mock.Mock(return_value=self.nova_client)
        self.backend.create_neutron_client = mock.Mock(return_value=self.neutron_client)
        self.backend.get_or_create_tenant = mock.Mock(return_value=self.tenant)
        self.backend.get_or_create_user = mock.Mock(return_value=('john', 'doe'))
        self.backend.get_or_create_network = mock.Mock()
        self.backend.ensure_user_is_tenant_admin = mock.Mock()

    def test_push_cloud_account_does_not_call_openstack_api(self):
        self.backend.push_cloud_account(self.cloud_account)

        self.assertFalse(self.backend.create_keystone_client.called, 'Keystone client should not have been created')
        self.assertFalse(self.backend.create_nova_client.called, 'Nova client should not have been created')

    def test_push_cloud_account_does_not_update_cloud_account(self):
        self.backend.push_cloud_account(self.cloud_account)

        self.assertFalse(self.cloud_account.save.called, 'Cloud account should not have been updated')

    def test_push_membership_synchronizes_user(self):
        self.backend.push_membership(self.membership)

        self.backend.get_or_create_user.assert_called_once_with(self.membership, self.keystone_client)

    def test_push_membership_synchronizes_tenant(self):
        self.backend.push_membership(self.membership)

        self.backend.get_or_create_tenant.assert_called_once_with(self.membership, self.keystone_client)

    def test_push_membership_synchronizes_network(self):
        self.backend.push_membership(self.membership)

        self.backend.get_or_create_network.assert_called_once_with(self.membership, self.neutron_client)

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
        self.backend.create_admin_session.side_effect = keystone_exceptions.AuthorizationFailure
        with self.assertRaises(CloudBackendError):
            self.backend.push_membership(self.membership)


class OpenStackBackendFlavorApiTest(TransactionTestCase):
    def setUp(self):
        self.nova_client = mock.Mock()
        self.nova_client.flavors.findall.return_value = []

        self.cloud_account = factories.CloudFactory()
        self.flavors = factories.FlavorFactory.create_batch(2, cloud=self.cloud_account)

        # Mock low level non-AbstractCloudBackend api methods
        self.backend = OpenStackBackend()
        self.backend.create_admin_session = mock.Mock()
        self.backend.create_nova_client = mock.Mock(return_value=self.nova_client)

    # TODO: Test pull_flavors uses proper credentials for nova
    def test_pull_flavors_queries_only_public_flavors(self):
        self.backend.pull_flavors(self.cloud_account)

        self.nova_client.flavors.findall.assert_called_once_with(
            is_public=True
        )

    def test_pull_flavors_creates_flavors_missing_in_database(self):
        # Given
        new_flavor = NovaFlavor(next_unique_flavor_id(), 'id1', 3, 5, 8)

        self.nova_client.flavors.findall.return_value = [
            nc_flavor_to_nova_flavor(self.flavors[0]),
            nc_flavor_to_nova_flavor(self.flavors[1]),
            new_flavor,
        ]

        # When
        self.backend.pull_flavors(self.cloud_account)

        # Then
        try:
            stored_flavor = self.cloud_account.flavors.get(flavor_id=new_flavor.id)

            self.assertEqual(stored_flavor.name, new_flavor.name)
            self.assertEqual(stored_flavor.cores, new_flavor.vcpus)
            self.assertEqual(stored_flavor.ram, new_flavor.ram * 1024)
            self.assertEqual(stored_flavor.disk, new_flavor.disk * 1024)
        except Flavor.DoesNotExist:
            self.fail('Flavor should have been created in the database')

    def test_pull_flavors_updates_matching_flavors(self):
        # Given
        def double_fields(flavor):
            return flavor._replace(
                name=flavor.name + 'foo',
                vcpus=flavor.vcpus * 2,
                ram=flavor.ram * 2,
                disk=flavor.disk * 2,
            )

        backend_flavors = [
            double_fields(nc_flavor_to_nova_flavor(self.flavors[0])),
            double_fields(nc_flavor_to_nova_flavor(self.flavors[1])),
        ]

        self.nova_client.flavors.findall.return_value = backend_flavors

        # When
        self.backend.pull_flavors(self.cloud_account)

        # Then
        for updated_flavor in backend_flavors:
            stored_flavor = self.cloud_account.flavors.get(flavor_id=updated_flavor.id)

            self.assertEqual(stored_flavor.name, updated_flavor.name)
            self.assertEqual(stored_flavor.cores, updated_flavor.vcpus)
            self.assertEqual(stored_flavor.ram, updated_flavor.ram * 1024)
            self.assertEqual(stored_flavor.disk, updated_flavor.disk * 1024)

    def test_pull_flavors_deletes_flavors_missing_in_backend(self):
        # Given
        self.nova_client.flavors.findall.return_value = [
            nc_flavor_to_nova_flavor(self.flavors[0]),
        ]

        # When
        self.backend.pull_flavors(self.cloud_account)

        # Then
        is_present = self.cloud_account.flavors.filter(
            flavor_id=self.flavors[1].flavor_id).exists()

        self.assertFalse(is_present, 'Flavor should have been deleted from the database')

    def test_pull_flavors_doesnt_delete_flavors_linked_to_instances(self):
        # Given
        iaas_factories.InstanceFactory.create(flavor=self.flavors[1])

        self.nova_client.flavors.findall.return_value = [
            nc_flavor_to_nova_flavor(self.flavors[0]),
        ]

        # When
        self.backend.pull_flavors(self.cloud_account)

        # Then
        is_present = self.cloud_account.flavors.filter(
            flavor_id=self.flavors[1].flavor_id).exists()

        self.assertTrue(is_present, 'Flavor should have not been deleted from the database')


class OpenStackBackendImageApiTest(TransactionTestCase):
    def setUp(self):
        self.glance_client = mock.Mock()

        #  C
        #  ^
        #  |
        # (I0)
        #  |
        #  v
        #  T0          T1        T2
        #  ^           ^         ^
        #  | \         | \       |
        #  |  \        |  \      |
        #  |   \       |   \     |
        #  v    v      v    v    v
        #  TM0  TM1    TM2  TM3  TM4
        #

        self.cloud_account = factories.CloudFactory()
        self.templates = iaas_factories.TemplateFactory.create_batch(3)

        self.template_mappings = (
            iaas_factories.TemplateMappingFactory.create_batch(2, template=self.templates[0]) +
            iaas_factories.TemplateMappingFactory.create_batch(2, template=self.templates[1]) +
            iaas_factories.TemplateMappingFactory.create_batch(1, template=self.templates[2])
        )

        self.image = iaas_factories.ImageFactory(
            cloud=self.cloud_account,
            template=self.template_mappings[0].template,
            backend_id=self.template_mappings[0].backend_image_id,
        )

        # Mock low level non-AbstractCloudBackend api methods
        self.backend = OpenStackBackend()
        self.backend.create_admin_session = mock.Mock()
        self.backend.create_glance_client = mock.Mock(return_value=self.glance_client)

    def test_pulling_creates_images_for_all_matching_template_mappings(self):
        # Given
        matching_mapping1 = self.template_mappings[2]
        image_id = matching_mapping1.backend_image_id
        new_image = GlanceImage(image_id, is_public=True, deleted=False)

        # Make another mapping use the same backend id
        matching_mapping2 = self.template_mappings[4]
        matching_mapping2.backend_image_id = image_id
        matching_mapping2.save()

        self.glance_client.images.list.return_value = iter([
            new_image,
        ])

        # When
        self.backend.pull_images(self.cloud_account)

        # Then
        image_count = self.cloud_account.images.filter(
            backend_id=new_image.id,
        ).count()

        self.assertEqual(2, image_count,
                         'Two images should have been created')

        try:
            self.cloud_account.images.get(
                backend_id=matching_mapping1.backend_image_id,
                template=matching_mapping1.template,
            )
        except Image.DoesNotExist:
            self.fail('Image for the first matching template mapping'
                      ' should have been created')

        try:
            self.cloud_account.images.get(
                backend_id=matching_mapping2.backend_image_id,
                template=matching_mapping2.template,
            )
        except Image.DoesNotExist:
            self.fail('Image for the second matching template mapping'
                      ' should have been created')

    def test_pulling_doesnt_create_images_missing_in_database_if_template_mapping_doesnt_exist(self):
        # Given
        non_matching_image = GlanceImage('not-mapped-id', is_public=True, deleted=False)

        self.glance_client.images.list.return_value = iter([
            non_matching_image,
        ])

        # When
        self.backend.pull_images(self.cloud_account)

        # Then
        image_exists = self.cloud_account.images.filter(
            backend_id=non_matching_image.id,
        ).exists()
        self.assertFalse(image_exists, 'Image should not have been created in the database')

    def test_pulling_doesnt_create_images_for_non_public_backend_images(self):
        # Given
        matching_mapping = self.template_mappings[2]
        image_id = matching_mapping.backend_image_id
        new_image = GlanceImage(image_id, is_public=False, deleted=False)

        self.glance_client.images.list.return_value = iter([
            new_image,
        ])

        # When
        self.backend.pull_images(self.cloud_account)

        # Then
        image_exists = self.cloud_account.images.filter(
            backend_id=new_image.id,
        ).exists()
        self.assertFalse(image_exists, 'Image should not have been created in the database')

    def test_pulling_doesnt_create_images_for_deleted_backend_images(self):
        # Given
        matching_mapping = self.template_mappings[2]
        image_id = matching_mapping.backend_image_id
        new_image = GlanceImage(image_id, is_public=True, deleted=True)

        self.glance_client.images.list.return_value = iter([
            new_image,
        ])

        # When
        self.backend.pull_images(self.cloud_account)

        # Then
        image_exists = self.cloud_account.images.filter(
            backend_id=new_image.id,
        ).exists()
        self.assertFalse(image_exists, 'Image should not have been created in the database')

    def test_pulling_does_not_create_image_if_backend_image_ids_collide(self):
        # Given
        matching_mapping1 = self.template_mappings[2]
        new_image1 = GlanceImage(matching_mapping1.backend_image_id, is_public=True, deleted=False)

        # Make another mapping use the same backend id
        matching_mapping2 = self.template_mappings[3]
        new_image2 = GlanceImage(matching_mapping2.backend_image_id, is_public=True, deleted=False)

        self.glance_client.images.list.return_value = iter([
            new_image1,
            new_image2,
        ])

        # When
        self.backend.pull_images(self.cloud_account)

        # Then
        images_exist = self.cloud_account.images.filter(
            template=self.templates[1]
        ).exists()

        self.assertFalse(images_exist,
                         'No images should have been created')

    def test_pulling_deletes_existing_image_if_template_mapping_doesnt_exist(self):
        # Given

        non_matching_image = GlanceImage('not-mapped-id', is_public=True, deleted=False)

        self.glance_client.images.list.return_value = iter([
            non_matching_image,
        ])

        # When
        self.backend.pull_images(self.cloud_account)

        # Then
        matching_mapping = self.template_mappings[0]

        image_exists = self.cloud_account.images.filter(
            backend_id=matching_mapping.backend_image_id,
            template=matching_mapping.template,
        ).exists()

        self.assertFalse(image_exists, 'Image should have been deleted')

    def test_pulling_updates_existing_images_backend_id_if_template_mapping_changed(self):
        # Given

        # Simulate MO updating the mapping
        matching_mapping = self.template_mappings[0]
        image_id = 'new-id'
        matching_mapping.backend_image_id = image_id
        matching_mapping.save()

        existing_image = GlanceImage(image_id, is_public=True, deleted=False)

        self.glance_client.images.list.return_value = iter([
            existing_image,
        ])

        # When
        self.backend.pull_images(self.cloud_account)

        # Then
        try:
            self.cloud_account.images.get(
                backend_id=matching_mapping.backend_image_id,
                template=matching_mapping.template,
            )
        except Image.DoesNotExist:
            self.fail("Image's backend_id should have been updated")


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
        self.backend.create_user_session = mock.Mock()

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
        self.backend.create_user_session = mock.Mock(side_effect=keystone_exceptions.AuthorizationFailure)

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
