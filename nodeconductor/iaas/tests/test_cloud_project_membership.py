from __future__ import unicode_literals

from mock import patch

from django.core.urlresolvers import reverse
from rest_framework import status
from rest_framework import test

from nodeconductor.iaas import models
from nodeconductor.iaas.tests import factories
from nodeconductor.core.models import SynchronizationStates
from nodeconductor.structure.models import CustomerRole, ProjectRole, ProjectGroupRole
from nodeconductor.structure.tests import factories as structure_factories


# noinspection PyMethodMayBeStatic
class UrlResolverMixin(object):

    def _get_project_url(self, project):
        return 'http://testserver' + reverse('project-detail', kwargs={'uuid': project.uuid})

    def _get_cloud_url(self, cloud):
        return 'http://testserver' + reverse('cloud-detail', kwargs={'uuid': cloud.uuid})


class CloudProjectMembershipCreateDeleteTest(UrlResolverMixin, test.APISimpleTestCase):

    def setUp(self):
        self.owner = structure_factories.UserFactory(is_staff=True, is_superuser=True)
        self.customer = structure_factories.CustomerFactory()
        self.customer.add_user(self.owner, CustomerRole.OWNER)

        self.project = structure_factories.ProjectFactory(customer=self.customer)
        self.cloud = factories.CloudFactory(
            auth_url='http://some-unique-example.com:5000/v231', customer=self.customer)

    def test_membership_creation(self):
        self.client.force_authenticate(self.owner)
        url = factories.CloudProjectMembershipFactory.get_list_url()
        data = {
            'cloud': self._get_cloud_url(self.cloud),
            'project': self._get_project_url(self.project)
        }

        with patch('nodeconductor.iaas.tasks.sync_cloud_membership.delay') as mocked_task:
            response = self.client.post(url, data)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            membership = models.CloudProjectMembership.objects.get(project=self.project, cloud=self.cloud)
            mocked_task.assert_called_with(membership.pk, is_membership_creation=True)
            # duplicate call should result in 400 code
            response = self.client.post(url, data)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_default_availability_zone_from_openstack_conf(self):
        nc_settings = {'OPENSTACK_CREDENTIALS': ({'auth_url': self.cloud.auth_url,
                                                  'default_availability_zone': 'zone1'},
                                                 {'auth_url': 'another_url2',
                                                  'default_availability_zone': 'zone2'})}
        self._check_membership_availability_zone(nc_settings, 'zone1')

    def test_availability_zone_provided_by_user_overrides_default_availability_zone(self):
        nc_settings = {'OPENSTACK_CREDENTIALS': ({'auth_url': self.cloud.auth_url,
                                                  'default_availability_zone': 'zone1'},)}
        self._check_membership_availability_zone(nc_settings, 'zone2', 'zone2')

    # Helper methods
    def _check_membership_availability_zone(self, nc_settings, output_value, input_value=''):
        self.client.force_authenticate(self.owner)
        url = factories.CloudProjectMembershipFactory.get_list_url()
        data = {
            'cloud': self._get_cloud_url(self.cloud),
            'project': self._get_project_url(self.project)
        }

        for args in nc_settings['OPENSTACK_CREDENTIALS']:
            auth_url = args.pop('auth_url')
            args['availability_zone'] = args.pop('default_availability_zone', '')
            models.OpenStackSettings.objects.update_or_create(auth_url=auth_url, defaults=args)

        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        membership = models.CloudProjectMembership.objects.get(project=self.project, cloud=self.cloud)

        if input_value:
            membership.availability_zone = input_value
            membership.save()

        self.assertEqual(membership.availability_zone, output_value)


class CloudProjectMembershipActionsTest(test.APISimpleTestCase):

    def setUp(self):
        self.staff = structure_factories.UserFactory(is_staff=True)
        self.cloud_project_membership = factories.CloudProjectMembershipFactory(state=SynchronizationStates.IN_SYNC)

    @patch('nodeconductor.iaas.tasks.push_cloud_membership_quotas')
    def test_staff_can_set_cloud_project_membership_quotas(self, mocked_task):
        self.client.force_authenticate(self.staff)
        url = factories.CloudProjectMembershipFactory.get_url(self.cloud_project_membership, 'set_quotas')
        quotas_data = {'security_group_count': 100, 'security_group_rule_count': 100}
        response = self.client.post(url, data=quotas_data)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        mocked_task.delay.assert_called_once_with(self.cloud_project_membership.pk, quotas=quotas_data)

    @patch('nodeconductor.iaas.tasks.push_cloud_membership_quotas')
    def test_volume_and_snapshot_quotas_are_created_with_max_instances_quota(self, mocked_task):
        nc_settings = {'OPENSTACK_QUOTAS_INSTANCE_RATIOS': {'volumes': 2, 'snapshots': 10}}

        with self.settings(NODECONDUCTOR=nc_settings):
            self.client.force_authenticate(self.staff)
            url = factories.CloudProjectMembershipFactory.get_url(self.cloud_project_membership, 'set_quotas')
            quotas_data = {'max_instances': 10}
            response = self.client.post(url, data=quotas_data)

            quotas_data['volumes'] = 20
            quotas_data['snapshots'] = 100

            self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
            mocked_task.delay.assert_called_once_with(self.cloud_project_membership.pk, quotas=quotas_data)

    @patch('nodeconductor.iaas.tasks.push_cloud_membership_quotas')
    def test_volume_and_snapshot_quotas_are_not_created_without_max_instances_quota(self, mocked_task):
        self.client.force_authenticate(self.staff)

        url = factories.CloudProjectMembershipFactory.get_url(self.cloud_project_membership, 'set_quotas')
        quotas_data = {'security_group_count': 100}
        response = self.client.post(url, data=quotas_data)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        mocked_task.delay.assert_called_once_with(self.cloud_project_membership.pk, quotas=quotas_data)

    @patch('nodeconductor.iaas.tasks.push_cloud_membership_quotas')
    def test_volume_and_snapshot_values_not_provided_in_settings_use_default_values(self, mocked_task):
        nc_settings = {}

        with self.settings(NODECONDUCTOR=nc_settings):
            self.client.force_authenticate(self.staff)
            url = factories.CloudProjectMembershipFactory.get_url(self.cloud_project_membership, 'set_quotas')
            quotas_data = {'max_instances': 10}
            response = self.client.post(url, data=quotas_data)

            quotas_data['volumes'] = 40
            quotas_data['snapshots'] = 200

            self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
            mocked_task.delay.assert_called_once_with(self.cloud_project_membership.pk, quotas=quotas_data)

    @patch('nodeconductor.iaas.tasks.create_external_network')
    def test_staff_user_can_create_external_network(self, mocked_task):
        self.client.force_authenticate(user=self.staff)
        url = factories.CloudProjectMembershipFactory.get_url(self.cloud_project_membership, 'external_network')
        data = {
            'vlan_id': '2007',
            'network_ip': '10.7.122.0',
            'network_prefix': 26,
            'ips_count': 6
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        mocked_task.delay.assert_called_once_with(str(self.cloud_project_membership.pk), data)

    @patch('nodeconductor.iaas.tasks.delete_external_network')
    def test_staff_user_can_delete_existent_external_network(self, mocked_task):
        self.cloud_project_membership.external_network_id = 'abcd1234'
        self.cloud_project_membership.save()
        self.client.force_authenticate(user=self.staff)

        url = factories.CloudProjectMembershipFactory.get_url(self.cloud_project_membership, 'external_network')
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        mocked_task.delay.assert_called_once_with(str(self.cloud_project_membership.pk))

    @patch('nodeconductor.iaas.tasks.delete_external_network')
    def test_staff_user_cannot_delete_not_existent_external_network(self, mocked_task):
        self.client.force_authenticate(user=self.staff)

        url = factories.CloudProjectMembershipFactory.get_url(self.cloud_project_membership, 'external_network')
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(mocked_task.delay.called)

    @patch('nodeconductor.iaas.tasks.allocate_floating_ip')
    def test_user_cannot_allocate_floating_ip_from_cpm_without_external_network_id(self, mocked_task):
        self.client.force_authenticate(user=self.staff)

        url = factories.CloudProjectMembershipFactory.get_url(self.cloud_project_membership, 'allocate_floating_ip')
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data['detail'], 'Cloud project membership should have an external network ID.')
        self.assertFalse(mocked_task.delay.called)

    @patch('nodeconductor.iaas.tasks.allocate_floating_ip')
    def test_user_cannot_allocate_floating_ip_from_cpm_in_unstable_state(self, mocked_task):
        self.client.force_authenticate(user=self.staff)

        cpm = factories.CloudProjectMembershipFactory(external_network_id='12345', state=SynchronizationStates.ERRED)
        url = factories.CloudProjectMembershipFactory.get_url(cpm, 'allocate_floating_ip')
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data['detail'], 'Cloud project membership must be in stable state.')
        self.assertFalse(mocked_task.delay.called)

    @patch('nodeconductor.iaas.tasks.allocate_floating_ip')
    def test_user_can_allocate_floating_ip_from_cpm_with_external_network_id(self, mocked_task):
        self.client.force_authenticate(user=self.staff)

        cpm = factories.CloudProjectMembershipFactory(external_network_id='12345', state=SynchronizationStates.IN_SYNC)
        url = factories.CloudProjectMembershipFactory.get_url(cpm, 'allocate_floating_ip')
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data['detail'], 'Floating IP allocation has been scheduled.')
        self.assertTrue(mocked_task.delay.called)


# XXX: this have to be reworked to permissions test
class ProjectCloudApiPermissionTest(UrlResolverMixin, test.APITransactionTestCase):
    def setUp(self):
        self.users = {
            'owner': structure_factories.UserFactory(),
            'admin': structure_factories.UserFactory(),
            'manager': structure_factories.UserFactory(),
            'group_manager': structure_factories.UserFactory(),
            'no_role': structure_factories.UserFactory(),
            'not_connected': structure_factories.UserFactory(),
        }

        # a single customer
        self.customer = structure_factories.CustomerFactory()
        self.customer.add_user(self.users['owner'], CustomerRole.OWNER)

        # that has 3 users connected: admin, manager, group_manager
        self.connected_project = structure_factories.ProjectFactory(customer=self.customer)
        self.connected_project.add_user(self.users['admin'], ProjectRole.ADMINISTRATOR)
        self.connected_project.add_user(self.users['manager'], ProjectRole.MANAGER)
        project_group = structure_factories.ProjectGroupFactory()
        project_group.projects.add(self.connected_project)
        project_group.add_user(self.users['group_manager'], ProjectGroupRole.MANAGER)

        # has defined a cloud and connected cloud to a project
        self.cloud = factories.CloudFactory(customer=self.customer)
        self.membership = factories.CloudProjectMembershipFactory(project=self.connected_project,
                                                                  cloud=self.cloud,
                                                                  state=SynchronizationStates.IN_SYNC)

        # the customer also has another project with users but without a permission link
        self.not_connected_project = structure_factories.ProjectFactory(customer=self.customer)
        self.not_connected_project.add_user(self.users['not_connected'], ProjectRole.ADMINISTRATOR)
        self.not_connected_project.save()

    def test_anonymous_user_cannot_grant_cloud_to_project(self):
        response = self.client.post(reverse('cloudproject_membership-list'), self._get_valid_payload())
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_can_connect_cloud_and_project_he_owns(self):
        user = self.users['owner']
        self.client.force_authenticate(user=user)

        cloud = factories.CloudFactory(customer=self.customer)
        project = structure_factories.ProjectFactory(customer=self.customer)

        payload = self._get_valid_payload(cloud, project)

        response = self.client.post(reverse('cloudproject_membership-list'), payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_group_manager_can_connect_project_and_cloud(self):
        user = self.users['group_manager']
        self.client.force_authenticate(user=user)

        cloud = factories.CloudFactory(customer=self.customer)
        project = self.connected_project
        payload = self._get_valid_payload(cloud, project)

        with patch('nodeconductor.iaas.tasks.sync_cloud_membership.delay'):
            response = self.client.post(reverse('cloudproject_membership-list'), payload)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_admin_cannot_connect_new_cloud_and_project_if_he_is_project_admin(self):
        user = self.users['admin']
        self.client.force_authenticate(user=user)

        cloud = factories.CloudFactory(customer=self.customer)
        project = self.connected_project
        payload = self._get_valid_payload(cloud, project)

        response = self.client.post(reverse('cloudproject_membership-list'), payload)
        # the new cloud should not be visible to the user
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertDictContainsSubset(
            {'cloud': ['Invalid hyperlink - Object does not exist.']}, response.data)

    def test_user_cannot_revoke_cloud_and_project_permission_if_he_is_project_manager(self):
        user = self.users['manager']
        self.client.force_authenticate(user=user)

        url = factories.CloudProjectMembershipFactory.get_url(self.membership)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_can_revoke_cloud_and_project_permission_if_he_is_project_group_manager(self):
        user = self.users['group_manager']
        self.client.force_authenticate(user=user)

        url = factories.CloudProjectMembershipFactory.get_url(self.membership)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_non_staff_user_cannot_request_cloud_project_link_quota_update(self):
        for user in self.users.values():
            self.client.force_authenticate(user=user)
            url = factories.CloudProjectMembershipFactory.get_url(self.membership, action='set_quotas')
            response = self.client.post(url)
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_user_can_request_cloud_project_link_quota_update(self):
        user = structure_factories.UserFactory(is_staff=True)
        self.client.force_authenticate(user=user)

        url = factories.CloudProjectMembershipFactory.get_url(self.membership, action='set_quotas')
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

    def test_user_cannot_modify_in_unstable_state(self):
        user = self.users['group_manager']
        self.client.force_authenticate(user=user)

        for state in SynchronizationStates.UNSTABLE_STATES:
            if state == SynchronizationStates.NEW:
                continue

            self.membership.state = state
            self.membership.save()

            url = factories.CloudProjectMembershipFactory.get_url(self.membership)
            response = self.client.delete(url)
            self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def _get_valid_payload(self, cloud=None, project=None):
        cloud = cloud or factories.CloudFactory()
        project = project or structure_factories.ProjectFactory()
        return {
            'cloud': self._get_cloud_url(cloud),
            'project': self._get_project_url(project)
        }
