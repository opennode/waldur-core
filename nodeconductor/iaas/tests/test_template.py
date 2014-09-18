from __future__ import unicode_literals

from rest_framework import status
from rest_framework import test
from rest_framework.reverse import reverse

from nodeconductor.cloud.tests import factories as cloud_factories
from nodeconductor.iaas.tests import factories as iaas_factories
from nodeconductor.structure.models import ProjectRole
from nodeconductor.structure.tests import factories as structure_factories


class TemplateApiPermissionTest(test.APITransactionTestCase):
    def setUp(self):
        self.users = {
            'staff': structure_factories.UserFactory(is_staff=True),
            'admin': structure_factories.UserFactory(is_staff=False),
            'manager': structure_factories.UserFactory(is_staff=False),
            'non_staff': structure_factories.UserFactory(is_staff=False),
        }

        self.templates = {
            'active': iaas_factories.TemplateFactory.create_batch(4, is_active=True),
            'inactive': [iaas_factories.TemplateFactory(is_active=False)],
        }

       #  Uadmin<-->P0      P1<--->Umgr
       #            ^       ^
       #            |       |
       #  +---------+       +---------+
       #  |         |       |         |
       #  v         v       v         v
       #  C0        C1      C2        C3
       #  ^         ^       ^         ^
       #  |         |\     /|         |
       #  |         |(I) (I)|         |
       #  |         |  \ /  |         |
       # (I)       (I)  x  (I)       (I)
       #  |         |  / \  |         |
       #  |         | /   \ |         |
       #  |         |/     \|         |
       #  v         v       v         v
       #  T0        T1      T2        T3

        project1 = structure_factories.ProjectFactory()
        project1.add_user(self.users['admin'], ProjectRole.ADMINISTRATOR)

        project2 = structure_factories.ProjectFactory(customer=project1.customer)
        project2.add_user(self.users['manager'], ProjectRole.MANAGER)

        self.clouds = cloud_factories.CloudFactory.create_batch(4, customer=project1.customer)
        project1.clouds.add(self.clouds[0], self.clouds[1])
        project2.clouds.add(self.clouds[2], self.clouds[3])

        for t, c in (
                (0, 0),
                (1, 1),
                (1, 2),
                (2, 1),
                (2, 2),
                (3, 3),
        ):
            iaas_factories.ImageFactory(template=self.templates['active'][t], cloud=self.clouds[c])

    # List filtration tests
    def test_anonymous_user_cannot_list_templates(self):
        response = self.client.get(reverse('template-list'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_staff_user_can_list_active_templates(self):
        self.client.force_authenticate(user=self.users['non_staff'])

        response = self.client.get(reverse('template-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        for template in self.templates['active']:
            template_url = self._get_template_url(template)
            self.assertIn(template_url, [template['url'] for template in response.data])

    def test_non_staff_user_cannot_list_inactive_templates(self):
        self.client.force_authenticate(user=self.users['non_staff'])

        response = self.client.get(reverse('template-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        for template in self.templates['inactive']:
            template_url = self._get_template_url(template)
            self.assertNotIn(template_url, [template['url'] for template in response.data])

    def test_staff_user_can_list_active_templates(self):
        self.client.force_authenticate(user=self.users['staff'])

        response = self.client.get(reverse('template-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        for template in self.templates['active']:
            template_url = self._get_template_url(template)
            self.assertIn(template_url, [template['url'] for template in response.data])

    def test_staff_user_can_list_inactive_templates(self):
        self.client.force_authenticate(user=self.users['staff'])

        response = self.client.get(reverse('template-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        for template in self.templates['inactive']:
            template_url = self._get_template_url(template)
            self.assertIn(template_url, [template['url'] for template in response.data])

    def test_staff_user_can_list_all_templates(self):
        self.client.force_authenticate(user=self.users['staff'])

        response = self.client.get(reverse('template-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        from itertools import chain

        for template in chain.from_iterable(self.templates.values()):
            template_url = self._get_template_url(template)
            self.assertIn(template_url, [template['url'] for template in response.data])

    def test_non_staff_user_can_filter_templates_by_cloud_he_has_access_to(self):
        tests = (
            # role, cloud index, resulting template indexes
            ('admin', 0, (0,)),
            ('admin', 1, (1, 2)),
            ('manager', 2, (1, 2)),
            ('manager', 3, (3,)),
        )

        for role, cloud_index, template_indexes in tests:
            self.client.force_authenticate(user=self.users[role])

            response = self.client.get(reverse('template-list'),
                                       {'cloud': self.clouds[cloud_index].uuid})
            self.assertEqual(response.status_code, status.HTTP_200_OK)

            expected_urls = [
                self._get_template_url(self.templates['active'][i])
                for i in template_indexes
            ]
            actual_urls = [template['url'] for template in response.data]

            self.assertEqual(sorted(expected_urls), sorted(actual_urls))

    def test_non_staff_user_gets_no_templates_when_filtering_by_cloud_he_has_no_access_to(self):
        tests = (
            # role, cloud index
            ('admin', 2),
            ('admin', 3),
            ('manager', 0),
            ('manager', 1),
        )

        for role, cloud_index in tests:
            self.client.force_authenticate(user=self.users[role])

            response = self.client.get(reverse('template-list'),
                                       {'cloud': self.clouds[cloud_index].uuid})
            self.assertEqual(response.status_code, status.HTTP_200_OK)

            self.assertEqual(0, len(response.data), 'User should see no templates')

    # Direct template access tests
    def test_anonymous_user_cannot_access_template(self):
        for template in self.templates['active']:
            response = self.client.get(self._get_template_url(template))
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_staff_user_can_access_active_templates(self):
        self.client.force_authenticate(user=self.users['non_staff'])

        for template in self.templates['active']:
            response = self.client.get(self._get_template_url(template))
            self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_non_staff_user_cannot_access_inactive_templates(self):
        self.client.force_authenticate(user=self.users['non_staff'])

        for template in self.templates['inactive']:
            response = self.client.get(self._get_template_url(template))
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_staff_user_can_access_active_templates(self):
        self.client.force_authenticate(user=self.users['staff'])

        for template in self.templates['active']:
            response = self.client.get(self._get_template_url(template))
            self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_staff_user_can_access_inactive_templates(self):
        self.client.force_authenticate(user=self.users['staff'])

        for template in self.templates['inactive']:
            response = self.client.get(self._get_template_url(template))
            self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_non_staff_user_cannot_see_is_active_template_field(self):
        self.client.force_authenticate(user=self.users['non_staff'])

        for template in self.templates['active']:
            response = self.client.get(self._get_template_url(template))
            self.assertNotIn('is_active', response.data)

    # Helper methods
    def _get_template_url(self, image):
        return 'http://testserver' + reverse('template-detail', kwargs={'uuid': image.uuid})

    # def _ensure_list_access_forbidden(self, user_role, image):
    #     self.client.force_authenticate(user=user_role)
    #
    #     response = self.client.get(reverse('template-list'))
    #     self.assertEqual(response.status_code, status.HTTP_200_OK)
    #
    #     image_url = self._get_template_url(self.templates[image])
    #     self.assertNotIn(image_url, [image['url'] for image in response.data])
    #
    # def _ensure_direct_access_forbidden(self, user_role, image):
    #     self.client.force_authenticate(user=user_role)
    #
    #     response = self.client.get(self._get_template_url(self.templates[image]))
    #     self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    #
    # def _get_valid_payload(self, resource):
    #     return {
    #         'architecture': resource.architecture,
    #         'cloud': 'http://testserver' + reverse('cloud-detail', kwargs={'uuid': resource.cloud.uuid}),
    #         'description': resource.description,
    #         'icon_url': resource.icon_url,
    #         'is_active': resource.is_active,
    #         'license': resource.license,
    #         'name': resource.name,
    #     }
