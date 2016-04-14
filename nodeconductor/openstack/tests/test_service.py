from mock import patch
from rest_framework import status, test

from nodeconductor.openstack import models
from nodeconductor.openstack.tests import factories
from nodeconductor.structure import SupportedServices
from nodeconductor.structure.models import ServiceSettings, ProjectRole, CustomerRole, ProjectGroupRole
from nodeconductor.structure.tests import factories as structure_factories


class ServicePermissionTest(test.APITransactionTestCase):
    def setUp(self):
        self.customers = {
            'owned': structure_factories.CustomerFactory(),
            'has_admined_project': structure_factories.CustomerFactory(),
            'has_managed_project': structure_factories.CustomerFactory(),
            'has_managed_by_group_manager': structure_factories.CustomerFactory(),
        }

        self.users = {
            'customer_owner': structure_factories.UserFactory(),
            'project_admin': structure_factories.UserFactory(),
            'project_manager': structure_factories.UserFactory(),
            'group_manager': structure_factories.UserFactory(),
            'no_role': structure_factories.UserFactory(),
        }

        self.projects = {
            'owned': structure_factories.ProjectFactory(customer=self.customers['owned']),
            'admined': structure_factories.ProjectFactory(customer=self.customers['has_admined_project']),
            'managed': structure_factories.ProjectFactory(customer=self.customers['has_managed_project']),
            'managed_by_group_manager': structure_factories.ProjectFactory(
                customer=self.customers['has_managed_by_group_manager']),
        }

        self.services = {
            'owned': factories.OpenStackServiceFactory(customer=self.customers['owned']),
            'admined': factories.OpenStackServiceFactory(customer=self.customers['has_admined_project']),
            'managed': factories.OpenStackServiceFactory(customer=self.customers['has_managed_project']),
            'managed_by_group_manager': factories.OpenStackServiceFactory(
                customer=self.customers['has_managed_by_group_manager']),
            'not_in_project': factories.OpenStackServiceFactory(),
        }

        self.settings = structure_factories.ServiceSettingsFactory(
            type=SupportedServices.Types.OpenStack, customer=self.customers['owned'])
        self.customers['owned'].add_user(self.users['customer_owner'], CustomerRole.OWNER)

        self.projects['admined'].add_user(self.users['project_admin'], ProjectRole.ADMINISTRATOR)
        self.projects['managed'].add_user(self.users['project_manager'], ProjectRole.MANAGER)
        project_group = structure_factories.ProjectGroupFactory()
        project_group.projects.add(self.projects['managed_by_group_manager'])
        project_group.add_user(self.users['group_manager'], ProjectGroupRole.MANAGER)

        factories.OpenStackServiceProjectLinkFactory(service=self.services['admined'], project=self.projects['admined'])
        factories.OpenStackServiceProjectLinkFactory(service=self.services['managed'], project=self.projects['managed'])
        factories.OpenStackServiceProjectLinkFactory(
            service=self.services['managed_by_group_manager'], project=self.projects['managed_by_group_manager'])

    # List filtration tests
    def test_anonymous_user_cannot_list_services(self):
        response = self.client.get(factories.OpenStackServiceFactory.get_list_url())
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_can_list_services_of_projects_he_is_administrator_of(self):
        self.client.force_authenticate(user=self.users['project_admin'])

        response = self.client.get(factories.OpenStackServiceFactory.get_list_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        service_url = factories.OpenStackServiceFactory.get_url(self.services['admined'])
        self.assertIn(service_url, [instance['url'] for instance in response.data])

    def test_user_can_list_services_of_projects_he_is_manager_of(self):
        self.client.force_authenticate(user=self.users['project_manager'])

        response = self.client.get(factories.OpenStackServiceFactory.get_list_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        service_url = factories.OpenStackServiceFactory.get_url(self.services['managed'])
        self.assertIn(service_url, [instance['url'] for instance in response.data])

    def test_user_can_list_services_of_projects_he_is_group_manager_of(self):
        self.client.force_authenticate(user=self.users['group_manager'])

        response = self.client.get(factories.OpenStackServiceFactory.get_list_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        service_url = factories.OpenStackServiceFactory.get_url(self.services['managed_by_group_manager'])
        self.assertIn(service_url, [instance['url'] for instance in response.data])

    def test_user_can_list_services_of_projects_he_is_customer_owner_of(self):
        self.client.force_authenticate(user=self.users['customer_owner'])

        response = self.client.get(factories.OpenStackServiceFactory.get_list_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        service_url = factories.OpenStackServiceFactory.get_url(self.services['owned'])
        self.assertIn(service_url, [instance['url'] for instance in response.data])

    def test_user_cannot_list_services_of_projects_he_has_no_role_in(self):
        self.client.force_authenticate(user=self.users['no_role'])

        response = self.client.get(factories.OpenStackServiceFactory.get_list_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        for service_type in 'admined', 'managed', 'managed_by_group_manager':
            service_url = factories.OpenStackServiceFactory.get_url(self.services[service_type])
            self.assertNotIn(
                service_url,
                [instance['url'] for instance in response.data],
                'User (role=none) should not see service (type=' + service_type + ')',
            )

    # Direct instance access tests
    def test_anonymous_user_cannot_access_service(self):
        for service_type in 'admined', 'managed', 'not_in_project':
            response = self.client.get(factories.OpenStackServiceFactory.get_url(self.services[service_type]))
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_can_access_service_allowed_for_project_he_is_administrator_of(self):
        self.client.force_authenticate(user=self.users['project_admin'])

        response = self.client.get(factories.OpenStackServiceFactory.get_url(self.services['admined']))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_can_access_service_allowed_for_project_he_is_manager_of(self):
        self.client.force_authenticate(user=self.users['project_manager'])

        response = self.client.get(factories.OpenStackServiceFactory.get_url(self.services['managed']))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_can_access_service_allowed_for_project_he_is_group_manager_of(self):
        self.client.force_authenticate(user=self.users['group_manager'])

        response = self.client.get(factories.OpenStackServiceFactory.get_url(self.services['managed_by_group_manager']))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_can_see_services_customer_name(self):
        self.client.force_authenticate(user=self.users['project_admin'])

        response = self.client.get(factories.OpenStackServiceFactory.get_url(self.services['admined']))

        customer = self.services['admined'].customer

        self.assertIn('customer', response.data)
        self.assertEqual(structure_factories.CustomerFactory.get_url(customer), response.data['customer'])

        self.assertIn('customer_name', response.data)
        self.assertEqual(customer.name, response.data['customer_name'])

    def test_user_cannot_access_service_allowed_for_project_he_has_no_role_in(self):
        self.client.force_authenticate(user=self.users['no_role'])

        for service_type in 'admined', 'managed':
            response = self.client.get(factories.OpenStackServiceFactory.get_url(self.services[service_type]))
            # 404 is used instead of 403 to hide the fact that the resource exists at all
            self.assertEqual(
                response.status_code,
                status.HTTP_404_NOT_FOUND,
                'User (role=none) should not see service (type=' + service_type + ')',
            )

    def test_user_cannot_access_service_not_allowed_for_any_project(self):
        for user_role in 'customer_owner', 'project_admin', 'project_manager', 'group_manager':
            self.client.force_authenticate(user=self.users[user_role])

            response = self.client.get(factories.OpenStackServiceFactory.get_url(self.services['not_in_project']))
            # 404 is used instead of 403 to hide the fact that the resource exists at all
            self.assertEqual(
                response.status_code,
                status.HTTP_404_NOT_FOUND,
                'User (role=' + user_role + ') should not see service (type=not_in_project)',
            )

    # Creation tests
    def test_user_can_add_service_to_the_customer_he_owns(self):
        self.client.force_authenticate(user=self.users['customer_owner'])

        payload = {
            'name': factories.OpenStackServiceFactory().name,
            'customer': structure_factories.CustomerFactory.get_url(self.customers['owned']),
            "backend_url": "http://example.com",
            "username": "user",
            "password": "secret",
        }

        with patch('nodeconductor.structure.executors.ServiceSettingsCreateExecutor.execute') as mocked:
            response = self.client.post(factories.OpenStackServiceFactory.get_list_url(), payload)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

            settings = ServiceSettings.objects.get(name=payload['name'])
            self.assertFalse(settings.shared)

            mocked.assert_any_call(settings)

    def test_user_cannot_add_service_to_the_customer_he_sees_but_doesnt_own(self):
        choices = {
            'project_admin': 'has_admined_project',
            'project_manager': 'has_managed_project',
        }
        for user_role, customer_type in choices.items():
            self.client.force_authenticate(user=self.users[user_role])

            new_service = factories.OpenStackServiceFactory.build(
                settings=self.settings, customer=self.customers[customer_type])
            response = self.client.post(factories.OpenStackServiceFactory.get_list_url(), self._get_valid_payload(new_service))
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_cannot_add_service_to_the_customer_he_has_no_role_in(self):
        self.client.force_authenticate(user=self.users['no_role'])

        new_service = factories.OpenStackServiceFactory.build(customer=self.customers['owned'])
        response = self.client.post(factories.OpenStackServiceFactory.get_list_url(), self._get_valid_payload(new_service))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_cannot_change_customer_of_service_he_owns(self):
        user = self.users['customer_owner']

        self.client.force_authenticate(user=user)

        service = self.services['owned']

        new_customer = structure_factories.CustomerFactory()
        new_customer.add_user(user, CustomerRole.OWNER)

        payload = {'customer': structure_factories.CustomerFactory.get_url(new_customer)}
        response = self.client.patch(factories.OpenStackServiceFactory.get_url(service), data=payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        reread_service = models.OpenStackService.objects.get(pk=service.pk)
        self.assertEqual(reread_service.customer, service.customer)

    def test_user_can_change_service_name_of_service_he_owns(self):
        self.client.force_authenticate(user=self.users['customer_owner'])

        service = self.services['owned']

        payload = {'name': 'new name'}
        response = self.client.patch(factories.OpenStackServiceFactory.get_url(service), data=payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

        reread_service = models.OpenStackService.objects.get(pk=service.pk)
        self.assertEqual(reread_service.name, 'new name')

    def _get_valid_payload(self, resource):
        return {
            'name': resource.name,
            'settings': structure_factories.ServiceSettingsFactory.get_url(resource.settings),
            'customer': structure_factories.CustomerFactory.get_url(resource.customer),
        }
