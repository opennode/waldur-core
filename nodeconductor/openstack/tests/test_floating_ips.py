from rest_framework import test, status

from nodeconductor.openstack.tests import factories
from nodeconductor.structure import models
from nodeconductor.structure.tests import factories as structure_factories


class FloatingIPListRetreiveTestCase(test.APITransactionTestCase):

    def setUp(self):
        # objects
        self.customer = structure_factories.CustomerFactory()
        self.project = structure_factories.ProjectFactory(customer=self.customer)
        self.service = factories.OpenStackServiceFactory(customer=self.customer)
        self.service_project_link = factories.OpenStackServiceProjectLinkFactory(service=self.service, project=self.project)
        self.active_ip = factories.FloatingIPFactory(status='ACTIVE', service_project_link=self.service_project_link)
        self.down_ip = factories.FloatingIPFactory(status='DOWN', service_project_link=self.service_project_link)
        self.other_ip = factories.FloatingIPFactory(status='UNDEFINED')
        # users
        self.staff = structure_factories.UserFactory(is_staff=True)
        self.owner = structure_factories.UserFactory()
        self.customer.add_user(self.owner, models.CustomerRole.OWNER)
        self.admin = structure_factories.UserFactory()
        self.project.add_user(self.admin, models.ProjectRole.ADMINISTRATOR)
        self.user = structure_factories.UserFactory()

    def test_floating_ip_list_can_be_filtered_by_project(self):
        data = {
            'project': self.project.uuid.hex,
        }
        # when
        self.client.force_authenticate(self.staff)
        response = self.client.get(factories.FloatingIPFactory.get_list_url(), data)
        # then
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_ip_uuids = [ip['uuid'] for ip in response.data]
        expected_ip_uuids = [ip.uuid.hex for ip in (self.active_ip, self.down_ip)]
        self.assertItemsEqual(response_ip_uuids, expected_ip_uuids)

    def test_floating_ip_list_can_be_filtered_by_service(self):
        data = {
            'service': self.service.uuid.hex,
        }
        # when
        self.client.force_authenticate(self.staff)
        response = self.client.get(factories.FloatingIPFactory.get_list_url(), data)
        # then
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_ip_uuids = [ip['uuid'] for ip in response.data]
        expected_ip_uuids = [ip.uuid.hex for ip in (self.active_ip, self.down_ip)]
        self.assertItemsEqual(response_ip_uuids, expected_ip_uuids)

    def test_floating_ip_list_can_be_filtered_by_status(self):
        data = {
            'status': 'ACTIVE',
        }
        # when
        self.client.force_authenticate(self.staff)
        response = self.client.get(factories.FloatingIPFactory.get_list_url(), data)
        # then
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_ip_uuids = [ip['uuid'] for ip in response.data]
        expected_ip_uuids = [self.active_ip.uuid.hex]
        self.assertItemsEqual(response_ip_uuids, expected_ip_uuids)

    def test_admin_receive_only_ips_from_his_project(self):
        # when
        self.client.force_authenticate(self.admin)
        response = self.client.get(factories.FloatingIPFactory.get_list_url())
        # then
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_ip_uuids = [ip['uuid'] for ip in response.data]
        expected_ip_uuids = [ip.uuid.hex for ip in (self.active_ip, self.down_ip)]
        self.assertItemsEqual(response_ip_uuids, expected_ip_uuids)

    def test_owner_receive_only_ips_from_his_customer(self):
        # when
        self.client.force_authenticate(self.owner)
        response = self.client.get(factories.FloatingIPFactory.get_list_url())
        # then
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_ip_uuids = [ip['uuid'] for ip in response.data]
        expected_ip_uuids = [ip.uuid.hex for ip in (self.active_ip, self.down_ip)]
        self.assertItemsEqual(response_ip_uuids, expected_ip_uuids)

    def test_regular_user_does_not_receive_any_ips(self):
        # when
        self.client.force_authenticate(self.user)
        response = self.client.get(factories.FloatingIPFactory.get_list_url())
        # then
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_ip_uuids = [ip['uuid'] for ip in response.data]
        expected_ip_uuids = []
        self.assertItemsEqual(response_ip_uuids, expected_ip_uuids)

    def test_admin_can_retreive_floating_ip_from_his_project(self):
        # when
        self.client.force_authenticate(self.admin)
        response = self.client.get(factories.FloatingIPFactory.get_url(self.active_ip))
        # then
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertItemsEqual(response.data['uuid'], self.active_ip.uuid.hex)

    def test_owner_can_not_retreive_floating_ip_not_from_his_customer(self):
        # when
        self.client.force_authenticate(self.owner)
        response = self.client.get(factories.FloatingIPFactory.get_url(self.other_ip))
        # then
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
