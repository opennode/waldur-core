from django.core.urlresolvers import reverse
from rest_framework import test, status

from nodeconductor.core.tests import helpers
from nodeconductor.structure import models
from nodeconductor.structure.tests import factories


def get_project_group_permission_url(permission):
    return 'http://testserver' + reverse('projectgroup_permission-detail', kwargs={'pk': permission.pk})


class TestGroupPermissionsCreateDelete(test.APITransactionTestCase):

    def setUp(self):
        self.customer = factories.CustomerFactory()
        self.project_group = factories.ProjectGroupFactory(customer=self.customer)
        self.project = factories.ProjectFactory(customer=self.customer)
        self.project_group.projects.add(self.project)

        self.owner = factories.UserFactory()
        self.staff = factories.UserFactory(is_staff=True)
        self.group_manager = factories.UserFactory()
        self.customer.add_user(self.owner, models.CustomerRole.OWNER)
        self.project_group.add_user(self.group_manager, models.ProjectGroupRole.MANAGER)

    def test_project_group_permission_creation(self):
        self.client.force_authenticate(self.owner)
        url = reverse('projectgroup_permission-list')
        project_group_url = factories.ProjectGroupFactory.get_url(self.project_group)
        user_url = factories.UserFactory.get_url()
        data = {
            'project_group': project_group_url,
            'user': user_url,
            'role': 'manager'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_project_group_permission_deletion(self):
        self.client.force_authenticate(self.owner)
        url = get_project_group_permission_url(self.project_group.roles.all()[0].permission_group)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_group_manager_cannot_create_permission_not_for_his_group(self):
        self.client.force_authenticate(self.group_manager)
        url = reverse('projectgroup_permission-list')
        project_group_url = factories.ProjectGroupFactory.get_url()
        user_url = factories.UserFactory.get_url()
        data = {
            'project_group': project_group_url,
            'user': user_url,
            'role': 'manager'
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {u'project_group': [u'Invalid hyperlink - object does not exist.']})


class TestGroupPermissionsListRetreive(test.APITransactionTestCase):

    def setUp(self):
        self.customer = factories.CustomerFactory()
        self.project_group = factories.ProjectGroupFactory(customer=self.customer)
        self.other_project_group = factories.ProjectGroupFactory()
        self.project = factories.ProjectFactory(customer=self.customer)
        self.project_group.projects.add(self.project)

        self.owner = factories.UserFactory()
        self.staff = factories.UserFactory(is_staff=True)
        self.group_manager = factories.UserFactory()
        self.customer.add_user(self.owner, models.CustomerRole.OWNER)
        self.project_group.add_user(self.group_manager, models.ProjectGroupRole.MANAGER)
        self.other_project_group.add_user(factories.UserFactory(), models.ProjectGroupRole.MANAGER)

    def test_owner_can_list_project_group_permissions_from_his_project_groups(self):
        self.client.force_authenticate(self.owner)
        url = reverse('projectgroup_permission-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(
            response.data[0]['url'],
            get_project_group_permission_url(self.project_group.roles.all()[0].permission_group))

    def test_staff_can_list_all_project_groups(self):
        self.client.force_authenticate(self.staff)
        url = reverse('projectgroup_permission-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_group_manager_can_list_project_group_permissions_from_his_project_groups(self):
        self.client.force_authenticate(self.group_manager)
        url = reverse('projectgroup_permission-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(
            response.data[0]['url'],
            get_project_group_permission_url(self.project_group.roles.all()[0].permission_group))

    def test_permission_contains_expected_fields(self):
        self.client.force_authenticate(self.staff)
        url = get_project_group_permission_url(self.project_group.roles.all()[0].permission_group)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expected_fields = [
            'url', 'role', 'project_group', 'project_group_name',
            'user', 'user_full_name', 'user_native_name'
        ]
        self.assertItemsEqual(response.data.keys(), expected_fields)


class TestGroupPermissionsPermissions(helpers.PermissionsTest):

    def setUp(self):
        self.customer = factories.CustomerFactory()
        self.project_group = factories.ProjectGroupFactory(customer=self.customer)
        self.other_project_group = factories.ProjectGroupFactory()
        self.project = factories.ProjectFactory(customer=self.customer)
        self.project_group.projects.add(self.project)

        self.owner = factories.UserFactory(username='owner')
        self.staff = factories.UserFactory(username='staff', is_staff=True, is_superuser=True)
        self.group_manager = factories.UserFactory(username='group_manager')
        self.customer.add_user(self.owner, models.CustomerRole.OWNER)
        self.project_group.add_user(self.group_manager, models.ProjectGroupRole.MANAGER)
        self.other_project_group.add_user(factories.UserFactory(), models.ProjectGroupRole.MANAGER)
        self.user = factories.UserFactory(username='regular user')

    def get_users_with_permission(self, url, method):
        if url != get_project_group_permission_url(self.other_project_group.roles.all()[0].permission_group):
            return [self.group_manager, self.owner, self.staff]
        return [self.staff]

    def get_users_without_permissions(self, url, method):
        if url == get_project_group_permission_url(self.other_project_group.roles.all()[0].permission_group):
            return [self.group_manager, self.owner, self.user]
        if url == reverse('projectgroup_permission-list'):
            return []
        return [self.user]

    def get_urls_configs(self):
        return [
            {
                'url': reverse('projectgroup_permission-list'),
                'method': 'GET',
            },
            {
                'url': reverse('projectgroup_permission-list'),
                'method': 'POST',
            },
            {
                'url': get_project_group_permission_url(self.project_group.roles.all()[0].permission_group),
                'method': 'GET',
            },
            {
                'url': get_project_group_permission_url(self.other_project_group.roles.all()[0].permission_group),
                'method': 'GET',
            },
            # TODO: enable this urls after correcting PermissionTest
            # {
            #     'url': get_project_group_permission_url(self.project_group.roles.all()[0].permission_group),
            #     'method': 'DELETE',
            # },
            # {
            #     'url': get_project_group_permission_url(self.other_project_group.roles.all()[0].permission_group),
            #     'method': 'DELETE',
            # },
        ]
