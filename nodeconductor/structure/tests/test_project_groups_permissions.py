from django.contrib.auth import get_user_model
from django.core.urlresolvers import reverse
from django.utils import unittest
from rest_framework import test, status

from mock import Mock

from nodeconductor.core.tests import helpers
from nodeconductor.structure import models, views
from nodeconductor.structure.tests import factories


User = get_user_model()


class ProjectGroupPermissionViewSetTest(unittest.TestCase):
    def setUp(self):
        self.view_set = views.ProjectGroupPermissionViewSet()
        self.request = Mock()
        self.user_group = Mock()

    def test_create_adds_user_role_to_project_group(self):
        project_group = self.user_group.group.projectgrouprole.project_group
        project_group.add_user.return_value = self.user_group, True

        serializer = Mock()
        serializer.is_valid.return_value = True
        serializer.object = self.user_group

        self.view_set.request = self.request
        self.view_set.can_save = Mock(return_value=True)
        self.view_set.get_serializer = Mock(return_value=serializer)
        self.view_set.create(self.request)

        project_group.add_user.assert_called_once_with(
            self.user_group.user,
            self.user_group.group.projectgrouprole.role_type,
        )

    def test_destroy_removes_user_role_from_project_group(self):
        project_group = self.user_group.group.projectgrouprole.project_group

        self.view_set.get_object = Mock(return_value=self.user_group)

        self.view_set.destroy(self.request)

        project_group.remove_user.assert_called_once_with(
            self.user_group.user,
            self.user_group.group.projectgrouprole.role_type,
        )


def get_project_group_permission_url(project_group_role):
    user = project_group_role.permission_group.user_set.first()
    role = models.ProjectGroupRole.MANAGER
    project_group = project_group_role.project_group

    permission = User.groups.through.objects.get(
        user=user,
        group__projectgrouprole__role_type=role,
        group__projectgrouprole__project_group=project_group,
    )
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
        url = get_project_group_permission_url(self.project_group.roles.first())
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


class TestGroupPermissionsListRetrieve(test.APITransactionTestCase):

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
            get_project_group_permission_url(self.project_group.roles.first()))

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
            get_project_group_permission_url(self.project_group.roles.first()))

    def test_permission_contains_expected_fields(self):
        self.client.force_authenticate(self.staff)
        url = get_project_group_permission_url(self.project_group.roles.first())
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
        if url != get_project_group_permission_url(self.other_project_group.roles.first()):
            return [self.group_manager, self.owner, self.staff]
        return [self.staff]

    def get_users_without_permissions(self, url, method):
        if url == get_project_group_permission_url(self.other_project_group.roles.first()):
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
                'url': get_project_group_permission_url(self.project_group.roles.first()),
                'method': 'GET',
            },
            {
                'url': get_project_group_permission_url(self.other_project_group.roles.first()),
                'method': 'GET',
            },
            # TODO: enable this urls after correcting PermissionTest
            # TODO: issue is that after deleting an entry with a user with permission rollback is not happening
            # manual testing has shown that permissions are correct
            # {
            #     'url': get_project_group_permission_url(self.project_group.roles.first()),
            #     'method': 'DELETE',
            # },
            # {
            #     'url': get_project_group_permission_url(self.other_project_group.roles.first()),
            #     'method': 'DELETE',
            # },
        ]
