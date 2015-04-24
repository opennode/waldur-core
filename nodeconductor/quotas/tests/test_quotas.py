from rest_framework import test, status

from nodeconductor.quotas import models
from nodeconductor.quotas.tests import factories


class QuotaListTest(test.APITransactionTestCase):

    def setUp(self):
        from nodeconductor.structure import models as structure_models
        from nodeconductor.structure.tests import factories as structure_factories
        from nodeconductor.iaas.tests import factories as iaas_factories

        self.customer = structure_factories.CustomerFactory()
        self.owner = structure_factories.UserFactory(username='owner')
        self.customer.add_user(self.owner, structure_models.CustomerRole.OWNER)

        self.owners_cloud = iaas_factories.CloudFactory(customer=self.customer)

        self.owners_memberships = [
            iaas_factories.CloudProjectMembershipFactory(cloud=self.owners_cloud) for _ in range(3)]
        self.other_memberships = [iaas_factories.CloudProjectMembershipFactory() for _ in range(3)]

    def test_owner_can_see_quotas_only_from_his_customer_memberships(self):
        self.client.force_authenticate(self.owner)

        response = self.client.get(factories.QuotaFactory.get_list_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_quotas_urls = [quota['url'] for quota in response.data]

        expected_quotas_urls = []
        for membership in self.owners_memberships:
            expected_quotas_urls += [factories.QuotaFactory.get_url(quota) for quota in membership.quotas.all()]
        not_expected_quotas_urls = []
        for membership in self.other_memberships:
            not_expected_quotas_urls += [factories.QuotaFactory.get_url(quota) for quota in membership.quotas.all()]

        for url in expected_quotas_urls:
            self.assertIn(url, response_quotas_urls)
        for url in not_expected_quotas_urls:
            self.assertNotIn(url, response_quotas_urls)

# XXX: This tests will be used with frontend quotas
# class QuotaUpdateTest(test.APITransactionTestCase):

#     def setUp(self):
#         from nodeconductor.structure import models as structure_models
#         from nodeconductor.structure.tests import factories as structure_factories
#         from nodeconductor.iaas.tests import factories as iaas_factories

#         self.customer = structure_factories.CustomerFactory()
#         self.owner = structure_factories.UserFactory(username='owner')
#         self.customer.add_user(self.owner, structure_models.CustomerRole.OWNER)

#         self.owners_cloud = iaas_factories.CloudFactory(customer=self.customer)

#         self.membership = iaas_factories.CloudProjectMembershipFactory(cloud=self.owners_cloud)
#         self.staff = structure_factories.UserFactory(is_staff=True)

#     def test_owner_cannot_update_membership_quotas(self):
#         quota = self.membership.quotas.all()[0]
#         self.client.force_authenticate(self.owner)
#         data = {'limit': 2048}

#         response = self.client.put(factories.QuotaFactory.get_url(quota), data=data)

#         self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

#     def test_staff_can_update_membership_quotas(self):
#         quota = self.membership.quotas.all()[0]
#         self.client.force_authenticate(self.staff)
#         data = {'limit': quota.limit + 10}

#         response = self.client.put(factories.QuotaFactory.get_url(quota), data=data)

#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#         reread_quota = models.Quota.objects.get(pk=quota.pk)
#         self.assertEqual(reread_quota.limit, data['limit'])
