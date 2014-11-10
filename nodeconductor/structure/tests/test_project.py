from __future__ import unicode_literals

from mock import call

from django.core.urlresolvers import reverse
from django.test import TransactionTestCase
from mock_django import mock_signal_receiver
from rest_framework import status
from rest_framework import test

from nodeconductor.structure import signals
from nodeconductor.structure.models import CustomerRole
from nodeconductor.structure.models import Project
from nodeconductor.structure.models import ProjectGroupRole
from nodeconductor.structure.models import ProjectRole
from nodeconductor.structure.tests import factories


class ProjectTest(TransactionTestCase):
    def setUp(self):
        self.project = factories.ProjectFactory()
        self.user = factories.UserFactory()

    def test_add_user_returns_created_if_grant_didnt_exist_before(self):
        _, created = self.project.add_user(self.user, ProjectRole.ADMINISTRATOR)

        self.assertTrue(created, 'Project permission should have been reported as created')

    def test_add_user_returns_not_created_if_grant_existed_before(self):
        self.project.add_user(self.user, ProjectRole.ADMINISTRATOR)
        _, created = self.project.add_user(self.user, ProjectRole.ADMINISTRATOR)

        self.assertFalse(created, 'Project permission should have been reported as not created')

    def test_add_user_returns_membership(self):
        membership, _ = self.project.add_user(self.user, ProjectRole.ADMINISTRATOR)

        self.assertEqual(membership.user, self.user)
        self.assertEqual(membership.group.projectrole.project, self.project)

    def test_add_user_returns_same_membership_for_consequent_calls_with_same_arguments(self):
        membership1, _ = self.project.add_user(self.user, ProjectRole.ADMINISTRATOR)
        membership2, _ = self.project.add_user(self.user, ProjectRole.ADMINISTRATOR)

        self.assertEqual(membership1, membership2)

    def test_add_user_emits_structure_role_granted_if_grant_didnt_exist_before(self):
        with mock_signal_receiver(signals.structure_role_granted) as receiver:
            self.project.add_user(self.user, ProjectRole.ADMINISTRATOR)

        receiver.assert_called_once_with(
            structure=self.project,
            user=self.user,
            role=ProjectRole.ADMINISTRATOR,

            sender=Project,
            signal=signals.structure_role_granted,
        )

    def test_add_user_doesnt_emit_structure_role_granted_if_grant_existed_before(self):
        self.project.add_user(self.user, ProjectRole.ADMINISTRATOR)

        with mock_signal_receiver(signals.structure_role_granted) as receiver:
            self.project.add_user(self.user, ProjectRole.ADMINISTRATOR)

        self.assertFalse(receiver.called, 'structure_role_granted should not be emitted')

    def test_remove_user_emits_structure_role_revoked_for_each_role_user_had_in_project(self):
        self.project.add_user(self.user, ProjectRole.ADMINISTRATOR)
        self.project.add_user(self.user, ProjectRole.MANAGER)

        with mock_signal_receiver(signals.structure_role_revoked) as receiver:
            self.project.remove_user(self.user)

        calls = [
            call(
                structure=self.project,
                user=self.user,
                role=ProjectRole.MANAGER,

                sender=Project,
                signal=signals.structure_role_revoked,
            ),

            call(
                structure=self.project,
                user=self.user,
                role=ProjectRole.ADMINISTRATOR,

                sender=Project,
                signal=signals.structure_role_revoked,
            ),
        ]

        receiver.assert_has_calls(calls, any_order=True)

        self.assertEqual(
            receiver.call_count, 2,
            'Excepted exactly 2 signals emitted'
        )

    def test_remove_user_emits_structure_role_revoked_if_grant_existed_before(self):
        self.project.add_user(self.user, ProjectRole.MANAGER)

        with mock_signal_receiver(signals.structure_role_revoked) as receiver:
            self.project.remove_user(self.user, ProjectRole.MANAGER)

        receiver.assert_called_once_with(
            structure=self.project,
            user=self.user,
            role=ProjectRole.MANAGER,

            sender=Project,
            signal=signals.structure_role_revoked,
        )

    def test_remove_user_doesnt_emit_structure_role_revoked_if_grant_didnt_exist_before(self):
        with mock_signal_receiver(signals.structure_role_revoked) as receiver:
            self.project.remove_user(self.user, ProjectRole.MANAGER)

        self.assertFalse(receiver.called, 'structure_role_remove should not be emitted')


def _get_valid_project_payload(resource=None):
    resource = resource or factories.ProjectFactory()
    return {
        'name': resource.name,
        'customer': 'http://testserver' + reverse('customer-detail', kwargs={'uuid': resource.customer.uuid}),
    }


class ProjectCreateUpdateDeleteTest(test.APITransactionTestCase):

    def setUp(self):
        self.staff = factories.UserFactory(is_staff=True)

        self.customer = factories.CustomerFactory()
        self.owner = factories.UserFactory()
        self.customer.add_user(self.owner, CustomerRole.OWNER)

        self.group_manager = factories.UserFactory()
        self.project_group = factories.ProjectGroupFactory(customer=self.customer)
        self.project_group.add_user(self.group_manager, ProjectGroupRole.MANAGER)

        self.project = factories.ProjectFactory(customer=self.customer)
        self.project_group.projects.add(self.project)

        self.admin = factories.UserFactory()
        self.project.add_user(self.admin, ProjectRole.ADMINISTRATOR)

        self.other_project = factories.ProjectFactory()

    # Create tests:
    def test_staff_can_create_any_project(self):
        self.client.force_authenticate(self.staff)

        data = _get_valid_project_payload()
        response = self.client.post(factories.ProjectFactory.get_list_url(), data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Project.objects.filter(name=data['name']).exists())

    def test_owner_can_create_project_belonging_to_the_customer_he_owns(self):
        self.client.force_authenticate(self.owner)

        data = _get_valid_project_payload(factories.ProjectFactory.create(customer=self.customer))
        response = self.client.post(factories.ProjectFactory.get_list_url(), data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Project.objects.filter(name=data['name']).exists())

    def test_owner_cannot_create_project_not_belonging_to_the_customer_he_owns(self):
        self.client.force_authenticate(self.owner)

        data = _get_valid_project_payload()
        response = self.client.post(factories.ProjectFactory.get_list_url(), data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_group_manager_can_create_project_belonging_to_his_group(self):
        self.client.force_authenticate(self.group_manager)

        data = _get_valid_project_payload(factories.ProjectFactory.create(customer=self.customer))
        data['project_groups'] = [factories.ProjectGroupFactory.get_url(self.project_group)]
        response = self.client.post(factories.ProjectFactory.get_list_url(), data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Project.objects.filter(name=data['name']).exists())

    def test_group_manager_cannot_create_project_with_not_his_group(self):
        self.client.force_authenticate(self.group_manager)

        data = _get_valid_project_payload(factories.ProjectFactory.create(customer=self.customer))
        data['project_groups'] = [factories.ProjectGroupFactory.get_url()]
        response = self.client.post(factories.ProjectFactory.get_list_url(), data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_group_manager_cannot_create_project_without_group(self):
        self.client.force_authenticate(self.group_manager)

        data = _get_valid_project_payload(factories.ProjectFactory.create(customer=self.customer))
        response = self.client.post(factories.ProjectFactory.get_list_url(), data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # Update tests:
    def test_user_can_change_single_project_field(self):
        self.client.force_authenticate(self.staff)

        response = self.client.patch(factories.ProjectFactory.get_url(self.project), {'name': 'New project name'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('New project name', response.data['name'])

    # Delete tests:
    def test_user_can_delete_project_belonging_to_the_customer_he_owns(self):
        self.client.force_authenticate(self.staff)

        response = self.client.delete(factories.ProjectFactory.get_url())
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)


class ProjectApiPermissionTest(test.APITransactionTestCase):
    forbidden_combinations = (
        # User role, Project
        ('admin', 'manager'),
        ('admin', 'inaccessible'),
        ('manager', 'admin'),
        ('manager', 'inaccessible'),
        ('no_role', 'admin'),
        ('no_role', 'manager'),
        ('no_role', 'inaccessible'),
    )

    def setUp(self):
        self.users = {
            'owner': factories.UserFactory(),
            'admin': factories.UserFactory(),
            'manager': factories.UserFactory(),
            'group_manager': factories.UserFactory(),
            'no_role': factories.UserFactory(),
            'multirole': factories.UserFactory(),
        }

        self.projects = {
            'owner': factories.ProjectFactory(),
            'admin': factories.ProjectFactory(),
            'manager': factories.ProjectFactory(),
            'group_manager': factories.ProjectFactory(),
            'inaccessible': factories.ProjectFactory(),
        }

        self.projects['admin'].add_user(self.users['admin'], ProjectRole.ADMINISTRATOR)
        self.projects['manager'].add_user(self.users['manager'], ProjectRole.MANAGER)

        self.projects['admin'].add_user(self.users['multirole'], ProjectRole.ADMINISTRATOR)
        self.projects['manager'].add_user(self.users['multirole'], ProjectRole.MANAGER)
        self.project_group = factories.ProjectGroupFactory()
        self.project_group.add_user(self.users['group_manager'], ProjectGroupRole.MANAGER)
        self.project_group.projects.add(self.projects['group_manager'])

        self.projects['owner'].customer.add_user(self.users['owner'], CustomerRole.OWNER)

    # TODO: Test for customer owners
    # Creation tests
    def test_anonymous_user_cannot_create_project(self):
        for old_project in self.projects.values():
            project = factories.ProjectFactory(customer=old_project.customer)
            response = self.client.post(reverse('project-list'), self._get_valid_payload(project))
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # List filtration tests
    def test_anonymous_user_cannot_list_projects(self):
        response = self.client.get(reverse('project-list'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_can_list_projects_belonging_to_customer_he_owns(self):
        self._ensure_list_access_allowed('owner')

    def test_user_can_list_projects_he_is_administrator_of(self):
        self._ensure_list_access_allowed('admin')

    def test_user_can_list_projects_he_is_manager_of(self):
        self._ensure_list_access_allowed('manager')

    def test_user_can_list_projects_he_is_group_manager_of(self):
        self._ensure_list_access_allowed('group_manager')

    def test_user_cannot_list_projects_he_has_no_role_in(self):
        for user_role, project in self.forbidden_combinations:
            self._ensure_list_access_forbidden(user_role, project)

    def test_user_can_filter_by_projects_where_he_has_manager_role(self):
        self.client.force_authenticate(user=self.users['multirole'])
        response = self.client.get(reverse('project-list') + '?can_manage')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        managed_project_url = self._get_project_url(self.projects['manager'])
        administrated_project_url = self._get_project_url(self.projects['admin'])

        self.assertIn(managed_project_url, [resource['url'] for resource in response.data])
        self.assertNotIn(administrated_project_url, [resource['url'] for resource in response.data])

    # Direct instance access tests
    def test_anonymous_user_cannot_access_project(self):
        project = factories.ProjectFactory()
        response = self.client.get(self._get_project_url(project))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_can_access_project_belonging_to_customer_he_owns(self):
        self._ensure_direct_access_allowed('owner')

    def test_user_can_access_project_he_is_administrator_of(self):
        self._ensure_direct_access_allowed('admin')

    def test_user_can_access_project_he_is_manager_of(self):
        self._ensure_direct_access_allowed('manager')

    def test_user_can_access_project_he_is_group_manager_of(self):
        self._ensure_direct_access_allowed('group_manager')

    def test_user_cannot_access_project_he_has_no_role_in(self):
        for user_role, project in self.forbidden_combinations:
            self._ensure_direct_access_forbidden(user_role, project)

    # Helper methods
    def _get_project_url(self, project):
        return 'http://testserver' + reverse('project-detail', kwargs={'uuid': project.uuid})

    def _get_valid_payload(self, resource=None):
        resource = resource or factories.ProjectFactory()
        return {
            'name': resource.name,
            'customer': 'http://testserver' + reverse('customer-detail', kwargs={'uuid': resource.customer.uuid}),
        }

    def _ensure_list_access_allowed(self, user_role):
        self.client.force_authenticate(user=self.users[user_role])

        response = self.client.get(reverse('project-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        project_url = self._get_project_url(self.projects[user_role])
        self.assertIn(project_url, [instance['url'] for instance in response.data])

    def _ensure_list_access_forbidden(self, user_role, project):
        self.client.force_authenticate(user=self.users[user_role])

        response = self.client.get(reverse('project-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        project_url = self._get_project_url(self.projects[project])
        self.assertNotIn(project_url, [resource['url'] for resource in response.data])

    def _ensure_direct_access_allowed(self, user_role):
        self.client.force_authenticate(user=self.users[user_role])
        response = self.client.get(self._get_project_url(self.projects[user_role]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def _ensure_direct_access_forbidden(self, user_role, project):
        self.client.force_authenticate(user=self.users[user_role])

        response = self.client.get(self._get_project_url(self.projects[project]))
        # 404 is used instead of 403 to hide the fact that the resource exists at all
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
