from rest_framework import status, test

from nodeconductor.iaas.tests import factories
from nodeconductor.structure.models import CustomerRole, ProjectRole
from nodeconductor.structure.tests import factories as structure_factories


class IpMappingPermissionTest(test.APITransactionTestCase):
    def setUp(self):
        self.users = {
            'owner': structure_factories.UserFactory(),
            'manager': structure_factories.UserFactory(),
            'admin': structure_factories.UserFactory(),
        }

        self.staff_user = structure_factories.UserFactory(is_staff=True)

        self.project = structure_factories.ProjectFactory()
        self.project.add_user(self.users['manager'], ProjectRole.MANAGER)
        self.project.add_user(self.users['admin'], ProjectRole.ADMINISTRATOR)

        self.project.customer.add_user(self.users['owner'], CustomerRole.OWNER)

        self.ip_mapping = factories.IpMappingFactory(project=self.project)

    # List filtration tests
    def test_user_cannot_list_ip_mappings_of_project_he_has_no_role_in(self):
        user = structure_factories.UserFactory()
        self.client.force_authenticate(user=user)

        response = self.client.get(factories.IpMappingFactory.get_list_url())
        urls = set([instance['url'] for instance in response.data])

        self.assertNotIn(factories.IpMappingFactory.get_url(self.ip_mapping), urls)

    def test_user_can_list_ip_mappings_of_project_he_has_role_in(self):
        for user_role in self.users:
            self._ensure_list_access_allowed(self.users[user_role])

    def test_staff_user_can_list_ip_mappings(self):
        self._ensure_list_access_allowed(self.staff_user)

    # Direct access tests
    def test_user_can_access_ip_mapping_of_project_he_has_role_in(self):
        for user_role in self.users:
            self._ensure_direct_access_allowed(self.users[user_role])

    def test_staff_user_can_access_ip_mapping(self):
        self._ensure_direct_access_allowed(self.staff_user)

    # Creation tests
    def test_user_cannot_create_ip_mapping_of_project_he_has_role_in(self):
        for user in self.users:
            self.client.force_authenticate(user=self.users[user])

            response = self.client.get(factories.IpMappingFactory.get_list_url())
            self.assertEqual(response.status_code, status.HTTP_200_OK)

            data = self._get_valid_payload(self.ip_mapping)

            response = self.client.post(factories.IpMappingFactory.get_list_url(), data)
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_user_can_create_ip_mapping(self):
        self.client.force_authenticate(self.staff_user)

        response = self.client.get(factories.IpMappingFactory.get_list_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = self._get_valid_payload()

        response = self.client.post(factories.IpMappingFactory.get_list_url(), data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    # Mutation tests
    def test_user_cannot_change_ip_mapping_of_project_he_has_role_in(self):
        for user_role in self.users:
            self.client.force_authenticate(self.users[user_role])

            data = self._get_valid_payload()

            response = self.client.put(factories.IpMappingFactory.get_url(self.ip_mapping), data)
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_user_can_change_ip_mapping(self):
            self.client.force_authenticate(self.staff_user)

            data = self._get_valid_payload()

            response = self.client.put(factories.IpMappingFactory.get_url(self.ip_mapping), data)
            self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_cannot_change_ip_mapping_single_field_of_project_he_has_role_in(self):
        for user_role in self.users:
            self.client.force_authenticate(self.users[user_role])

            data = {
                'public_ip': '1.2.3.4',
            }

            response = self.client.patch(factories.IpMappingFactory.get_url(self.ip_mapping), data)
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_user_can_change_ip_mapping_single_field(self):
            self.client.force_authenticate(self.staff_user)

            data = {
                'public_ip': '1.2.3.4',
            }

            response = self.client.patch(factories.IpMappingFactory.get_url(self.ip_mapping), data)
            self.assertEqual(response.status_code, status.HTTP_200_OK)

    # Deletion tests
    def test_user_cannot_delete_ip_mapping_of_project_he_has_role_in(self):
        for user_role in self.users:
            self.client.force_authenticate(self.users[user_role])

            response = self.client.delete(factories.IpMappingFactory.get_url(self.ip_mapping))
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_user_can_delete_ip_mapping(self):
        self.client.force_authenticate(self.staff_user)

        response = self.client.delete(factories.IpMappingFactory.get_url(self.ip_mapping))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    # Helpers method
    def _ensure_list_access_allowed(self, user):
        self.client.force_authenticate(user=user)

        response = self.client.get(factories.IpMappingFactory.get_list_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        urls = set([instance['url'] for instance in response.data])
        self.assertIn(factories.IpMappingFactory.get_url(self.ip_mapping), urls)

    def _ensure_direct_access_allowed(self, user):
        self.client.force_authenticate(user=user)

        response = self.client.get(factories.IpMappingFactory.get_url(self.ip_mapping))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def _get_valid_payload(self, ip_mapping=None):
        resource = ip_mapping or factories.IpMappingFactory()
        return {
            'public_ip': resource.public_ip,
            'private_ip': resource.private_ip,
            'project': structure_factories.ProjectFactory.get_url(resource.project)
        }


class IpMappingPermissionApiFiltrationTest(test.APISimpleTestCase):
    def setUp(self):
        user = structure_factories.UserFactory(is_staff=True)
        self.client.force_authenticate(user=user)

        self.ip_mappings = {
            'first': factories.IpMappingFactory(),
            'second': factories.IpMappingFactory(),
        }

    def test_staff_user_can_filter_ip_mappings_by_project_uuid(self):
        response = self.client.get(factories.IpMappingFactory.get_list_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        for ip_mapping in self.ip_mappings:
            project = self.ip_mappings[ip_mapping].project

            query = '?project=%s' % project.uuid

            response = self.client.get(factories.IpMappingFactory.get_list_url() + query)
            self.assertEqual(response.status_code, status.HTTP_200_OK)

            project_url = structure_factories.ProjectFactory.get_url(project)

            for instance in response.data:
                self.assertEqual(project_url, instance['project'])

    def test_staff_user_can_filter_ip_mappings_by_private_ip(self):
        for ip_mapping in self.ip_mappings:
            private_ip = self.ip_mappings[ip_mapping].private_ip
            self._ensure_matching_entries_in('private_ip', private_ip)

    def test_staff_user_can_filter_ip_mappings_by_public_ip(self):
        for ip_mapping in self.ip_mappings:
            public_ip = self.ip_mappings[ip_mapping].public_ip
            self._ensure_matching_entries_in('public_ip', public_ip)

    def _ensure_matching_entries_in(self, field, value):
        query = '?%s=%s' % (field, value)

        response = self.client.get(factories.IpMappingFactory.get_list_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.get(factories.IpMappingFactory.get_list_url() + query)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        for ip_mapping in response.data:
                self.assertEqual(value, ip_mapping[field])
