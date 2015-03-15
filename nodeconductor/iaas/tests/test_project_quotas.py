from __future__ import unicode_literals

from rest_framework import test

from nodeconductor.iaas.tests import factories
from nodeconductor.structure.tests import factories as structure_factories
from nodeconductor.structure.models import ProjectRole


class ProjectResourceQuotasTest(test.APITransactionTestCase):

    def setUp(self):
        # users
        self.admin = structure_factories.UserFactory()
        self.staff = structure_factories.UserFactory(is_staff=True)
        # project
        self.project = structure_factories.ProjectFactory()
        self.project.add_user(self.admin, ProjectRole.ADMINISTRATOR)
        # resource quotas
        quotas = [
            {'name': 'vcpu', 'usage': 5, 'limit': 10},
            {'name': 'ram', 'usage': 1024, 'limit': 2048},
            {'name': 'storage', 'usage': 512, 'limit': 20 * 1048},
            {'name': 'max_instances', 'usage': 5, 'limit': 10},
        ]
        self.membership1 = factories.CloudProjectMembershipFactory(project=self.project, quotas=quotas)
        self.membership2 = factories.CloudProjectMembershipFactory(project=self.project, quotas=quotas)

    def _execute_request_to_project(self, user):
        self.client.force_authenticate(user)
        return self.client.get(structure_factories.ProjectFactory.get_url(self.project))

    def test_project_returns_sum_of_membership_resource_quotas_usages(self):
        # when
        response = self._execute_request_to_project(self.staff)
        # then
        self.assertEqual(response.status_code, 200)
        quotas1 = self.membership1.quotas
        quotas2 = self.membership2.quotas

        expected_resource_quotas_usages = {
            'vcpu': quotas1.get(name='vcpu').usage + quotas2.get(name='vcpu').usage,
            'ram': quotas1.get(name='ram').usage + quotas2.get(name='ram').usage,
            'storage': quotas1.get(name='storage').usage + quotas2.get(name='storage').usage,
            'max_instances': quotas1.get(name='max_instances').usage + quotas2.get(name='max_instances').usage,
        }
        self.assertEqual(response.data['resource_quota_usage'], expected_resource_quotas_usages)
