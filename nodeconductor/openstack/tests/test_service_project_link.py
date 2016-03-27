from mock import patch
import unittest

from rest_framework import test, status

from nodeconductor.openstack import models
from nodeconductor.openstack.tests import factories
from nodeconductor.core.models import SynchronizationStates
from nodeconductor.structure.models import CustomerRole, ProjectRole, ProjectGroupRole
from nodeconductor.structure.tests import factories as structure_factories


class ServiceProjectLinkCreateDeleteTest(test.APISimpleTestCase):

    def setUp(self):
        self.owner = structure_factories.UserFactory(is_staff=True, is_superuser=True)
        self.customer = structure_factories.CustomerFactory()
        self.customer.add_user(self.owner, CustomerRole.OWNER)

        self.project = structure_factories.ProjectFactory(customer=self.customer)
        self.service = factories.OpenStackServiceFactory(customer=self.customer)

    def test_membership_creation(self):
        self.client.force_authenticate(self.owner)

        url = factories.OpenStackServiceProjectLinkFactory.get_list_url()
        payload = {
            'service': factories.OpenStackServiceFactory.get_url(self.service),
            'project': structure_factories.ProjectFactory.get_url(self.project)
        }

        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        models.OpenStackServiceProjectLink.objects.get(
            project=self.project, service=self.service)

        # duplicate call should result in 400 code
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


@unittest.skip('Test should be moved to tenant, after NC-1267')
class ServiceProjectLinkActionsTest(test.APISimpleTestCase):

    def setUp(self):
        self.staff = structure_factories.UserFactory(is_staff=True)
        self.service_project_link = factories.OpenStackServiceProjectLinkFactory(state=SynchronizationStates.IN_SYNC)

        self.quotas_url = factories.OpenStackServiceProjectLinkFactory.get_url(
            self.service_project_link, 'set_quotas')
        self.network_url = factories.OpenStackServiceProjectLinkFactory.get_url(
            self.service_project_link, 'external_network')
        self.ips_url = factories.OpenStackServiceProjectLinkFactory.get_url(
            self.service_project_link, 'allocate_floating_ip')

    def test_staff_can_set_service_project_membership_quotas(self):
        self.client.force_authenticate(self.staff)
        quotas_data = {'security_group_count': 100, 'security_group_rule_count': 100}

        with patch('celery.app.base.Celery.send_task') as mocked_task:
            response = self.client.post(self.quotas_url, data=quotas_data)
            self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
            mocked_task.assert_called_once_with(
                'nodeconductor.structure.sync_service_project_links',
                (self.service_project_link.to_string(),), {'quotas': quotas_data}, countdown=2)

    def test_volume_and_snapshot_quotas_are_created_with_max_instances_quota(self):
        self.client.force_authenticate(self.staff)
        nc_settings = {'OPENSTACK_QUOTAS_INSTANCE_RATIOS': {'volumes': 3, 'snapshots': 7}}
        quotas_data = {'instances': 10}

        with patch('celery.app.base.Celery.send_task') as mocked_task:
            with self.settings(NODECONDUCTOR=nc_settings):
                response = self.client.post(self.quotas_url, data=quotas_data)

                quotas_data['volumes'] = 30
                quotas_data['snapshots'] = 70

                self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
                mocked_task.assert_called_once_with(
                    'nodeconductor.structure.sync_service_project_links',
                    (self.service_project_link.to_string(),), {'quotas': quotas_data}, countdown=2)

    def test_volume_and_snapshot_quotas_are_not_created_without_max_instances_quota(self):
        self.client.force_authenticate(self.staff)
        quotas_data = {'security_group_count': 100}

        with patch('celery.app.base.Celery.send_task') as mocked_task:
            response = self.client.post(self.quotas_url, data=quotas_data)
            self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
            mocked_task.assert_called_once_with(
                'nodeconductor.structure.sync_service_project_links',
                (self.service_project_link.to_string(),), {'quotas': quotas_data}, countdown=2)

    def test_volume_and_snapshot_values_not_provided_in_settings_use_default_values(self):
        self.client.force_authenticate(self.staff)
        quotas_data = {'instances': 10}

        with patch('celery.app.base.Celery.send_task') as mocked_task:
            with self.settings(NODECONDUCTOR={}):
                response = self.client.post(self.quotas_url, data=quotas_data)

                quotas_data['volumes'] = 40
                quotas_data['snapshots'] = 200

                self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
                mocked_task.assert_called_once_with(
                    'nodeconductor.structure.sync_service_project_links',
                    (self.service_project_link.to_string(),), {'quotas': quotas_data}, countdown=2)

    def test_staff_user_can_create_external_network(self):
        self.client.force_authenticate(user=self.staff)
        payload = {
            'vlan_id': '2007',
            'network_ip': '10.7.122.0',
            'network_prefix': 26,
            'ips_count': 6
        }

        with patch('celery.app.base.Celery.send_task') as mocked_task:
            response = self.client.post(self.network_url, payload)
            self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
            mocked_task.assert_called_once_with(
                'nodeconductor.openstack.sync_external_network',
                (self.service_project_link.to_string(), 'create', payload), {}, countdown=2)

    def test_staff_user_can_delete_existent_external_network(self):
        self.service_project_link.external_network_id = 'abcd1234'
        self.service_project_link.save()
        self.client.force_authenticate(user=self.staff)

        with patch('celery.app.base.Celery.send_task') as mocked_task:
            response = self.client.delete(self.network_url)
            self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
            mocked_task.assert_called_once_with(
                'nodeconductor.openstack.sync_external_network',
                (self.service_project_link.to_string(), 'delete'), {}, countdown=2)

    def test_staff_user_cannot_delete_not_existent_external_network(self):
        self.client.force_authenticate(user=self.staff)
        self.service_project_link.external_network_id = ''
        self.service_project_link.save()

        with patch('celery.app.base.Celery.send_task') as mocked_task:
            response = self.client.delete(self.network_url)
            self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
            self.assertFalse(mocked_task.called)

    def test_user_cannot_allocate_floating_ip_from_spl_without_external_network_id(self):
        self.client.force_authenticate(user=self.staff)
        self.service_project_link.external_network_id = ''
        self.service_project_link.save()

        with patch('celery.app.base.Celery.send_task') as mocked_task:
            response = self.client.post(self.ips_url)
            self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
            self.assertEqual(response.data['detail'], 'Service project link should have an external network ID.')
            self.assertFalse(mocked_task.called)

    def test_user_cannot_allocate_floating_ip_from_spl_in_unstable_state(self):
        self.client.force_authenticate(user=self.staff)
        spl = factories.OpenStackServiceProjectLinkFactory(
            external_network_id='12345', state=SynchronizationStates.ERRED)
        url = factories.OpenStackServiceProjectLinkFactory.get_url(spl, 'allocate_floating_ip')

        with patch('celery.app.base.Celery.send_task') as mocked_task:
            response = self.client.post(url)
            self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
            self.assertEqual(response.data['detail'], 'Tenant should be in state OK.')
            self.assertFalse(mocked_task.delay.called)

    def test_user_can_allocate_floating_ip_from_spl_with_external_network_id(self):
        self.client.force_authenticate(user=self.staff)
        spl = factories.OpenStackServiceProjectLinkFactory(
            external_network_id='12345', state=SynchronizationStates.IN_SYNC)
        url = factories.OpenStackServiceProjectLinkFactory.get_url(spl, 'allocate_floating_ip')

        with patch('celery.app.base.Celery.send_task') as mocked_task:
            response = self.client.post(url)
            self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
            self.assertEqual(response.data['detail'], 'Floating IP allocation has been scheduled.')

            mocked_task.assert_called_once_with(
                'nodeconductor.openstack.allocate_floating_ip',
                (spl.to_string(),), {}, countdown=2)


class ProjectCloudApiPermissionTest(test.APITransactionTestCase):
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

        # has defined a service and connected service to a project
        self.service = factories.OpenStackServiceFactory(customer=self.customer)
        self.service_project_link = factories.OpenStackServiceProjectLinkFactory(
            project=self.connected_project,
            service=self.service,
            state=SynchronizationStates.IN_SYNC)

        # the customer also has another project with users but without a permission link
        self.not_connected_project = structure_factories.ProjectFactory(customer=self.customer)
        self.not_connected_project.add_user(self.users['not_connected'], ProjectRole.ADMINISTRATOR)
        self.not_connected_project.save()

        self.url = factories.OpenStackServiceProjectLinkFactory.get_list_url()

    def test_anonymous_user_cannot_grant_service_to_project(self):
        response = self.client.post(self.url, self._get_valid_payload())
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_can_connect_service_and_project_he_owns(self):
        user = self.users['owner']
        self.client.force_authenticate(user=user)

        service = factories.OpenStackServiceFactory(customer=self.customer)
        project = structure_factories.ProjectFactory(customer=self.customer)

        payload = self._get_valid_payload(service, project)

        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_group_manager_can_connect_project_and_service(self):
        user = self.users['group_manager']
        self.client.force_authenticate(user=user)

        service = factories.OpenStackServiceFactory(customer=self.customer)
        project = self.connected_project
        payload = self._get_valid_payload(service, project)

        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_admin_cannot_connect_new_service_and_project_if_he_is_project_admin(self):
        user = self.users['admin']
        self.client.force_authenticate(user=user)

        service = factories.OpenStackServiceFactory(customer=self.customer)
        project = self.connected_project
        payload = self._get_valid_payload(service, project)

        response = self.client.post(self.url, payload)
        # the new service should not be visible to the user
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertDictContainsSubset(
            {'service': ['Invalid hyperlink - Object does not exist.']}, response.data)

    def test_user_cannot_revoke_service_and_project_permission_if_he_is_project_manager(self):
        user = self.users['manager']
        self.client.force_authenticate(user=user)

        url = factories.OpenStackServiceProjectLinkFactory.get_url(self.service_project_link)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_can_revoke_service_and_project_permission_if_he_is_project_group_manager(self):
        user = self.users['group_manager']
        self.client.force_authenticate(user=user)

        url = factories.OpenStackServiceProjectLinkFactory.get_url(self.service_project_link)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    @unittest.skip('Test should be moved to tenant, after NC-1267')
    def test_non_staff_user_cannot_request_service_project_link_quota_update(self):
        for user in self.users.values():
            self.client.force_authenticate(user=user)
            url = factories.OpenStackServiceProjectLinkFactory.get_url(self.service_project_link, action='set_quotas')
            response = self.client.post(url)
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @unittest.skip('Test should be moved to tenant, after NC-1267')
    def test_staff_user_can_request_service_project_link_quota_update(self):
        user = structure_factories.UserFactory(is_staff=True)
        self.client.force_authenticate(user=user)

        url = factories.OpenStackServiceProjectLinkFactory.get_url(self.service_project_link, action='set_quotas')
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

    def _get_valid_payload(self, service=None, project=None):
        return {
            'service': factories.OpenStackServiceFactory.get_url(service),
            'project': structure_factories.ProjectFactory.get_url(project)
        }
