from rest_framework import test

from nodeconductor.structure import models
from nodeconductor.structure.tests import factories


class ResourceQuotasTest(test.APITransactionTestCase):
    # XXX: This tests add dependencies from 'iaas' application. They should be removed or refactored.

    def setUp(self):
        # users
        self.admin = factories.UserFactory()
        self.staff = factories.UserFactory(is_staff=True)
        # project
        self.project = factories.ProjectFactory()
        self.project.add_user(self.admin, models.ProjectRole.ADMINISTRATOR)
        from nodeconductor.iaas.tests import factories as iaas_factories
        # resource quotas
        self.membership = iaas_factories.CloudProjectMembershipFactory(project=self.project)
        self.quota = iaas_factories.ResourceQuotaFactory(cloud_project_membership=self.membership)
        self.quota2 = iaas_factories.ResourceQuotaFactory(cloud_project_membership=self.membership)
        self.quota_usage = iaas_factories.ResourceQuotaUsageFactory(cloud_project_membership=self.membership)

    def _execute_request_to_project(self, user):
        self.client.force_authenticate(user)
        return self.client.get(factories.ProjectFactory.get_url(self.project))

    def test_project_returns_sum_of_membership_resource_quotas(self):
        # when
        response = self._execute_request_to_project(self.admin)
        # then
        self.assertEqual(response.status_code, 200)
        expected_resource_quotas = {
            'vcpu': self.quota.vcpu + self.quota2.vcpu,
            'ram': self.quota.ram + self.quota2.ram,
            'storage': self.quota.storage + self.quota2.storage,
            'max_instances': self.quota.max_instances + self.quota2.max_instances,
            'backup_storage': self.quota.backup_storage + self.quota2.backup_storage,
        }
        self.assertEqual(response.data['resource_quota'], expected_resource_quotas)

    def test_project_returns_sum_of_membership_resource_quotas_usages(self):
        # when
        response = self._execute_request_to_project(self.staff)
        # then
        self.assertEqual(response.status_code, 200)
        expected_resource_quotas_usages = {
            'vcpu_usage': self.quota_usage.vcpu,
            'ram_usage': self.quota_usage.ram,
            'storage_usage': self.quota_usage.storage,
            'max_instances_usage': self.quota_usage.max_instances,
            'backup_storage_usage': self.quota_usage.backup_storage,
        }
        self.assertEqual(response.data['resource_quota_usage'], expected_resource_quotas_usages)
