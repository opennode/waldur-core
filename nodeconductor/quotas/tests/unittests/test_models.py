import random

from django.test import TestCase

from nodeconductor.iaas import models as iaas_models
from nodeconductor.iaas.tests import factories as iaas_factories


class QuotaModelMixinTest(TestCase):
    def test_all_values_are_positive(self):
        # we have 3 memberships:
        memberships = iaas_factories.CloudProjectMembershipFactory.create_batch(3)

        # each membership has non zero quotas:
        for membership in memberships:
            for quota_name in membership.QUOTAS_NAMES:
                limit = random.choice([10, 20, 30, 40])
                membership.set_quota_limit(quota_name, limit)
                membership.set_quota_usage(quota_name, limit / 2)
        owners = memberships[:2]

        sum_of_quotas = iaas_models.CloudProjectMembership.get_sum_of_quotas_as_dict(owners)

        expected_sum_of_quotas = {}
        for quota_name in iaas_models.CloudProjectMembership.QUOTAS_NAMES:
            expected_sum_of_quotas[quota_name] = sum(owner.quotas.get(name=quota_name).limit for owner in owners)
            expected_sum_of_quotas[quota_name + '_usage'] = sum(
                owner.quotas.get(name=quota_name).usage for owner in owners)

        self.assertEqual(expected_sum_of_quotas, sum_of_quotas)

    def test_some_limit_is_negative(self):
        memberships = iaas_factories.CloudProjectMembershipFactory.create_batch(3)
        memberships[0].set_quota_limit('vcpu', -1)
        memberships[1].set_quota_limit('vcpu', 10)
        memberships[2].set_quota_limit('vcpu', 30)

        sum_of_quotas = iaas_models.CloudProjectMembership.get_sum_of_quotas_as_dict(
            memberships, quota_names=['vcpu'], fields=['limit'])
        self.assertEqual({'vcpu': 40}, sum_of_quotas)

    def test_all_limits_are_negative(self):
        memberships = iaas_factories.CloudProjectMembershipFactory.create_batch(3)
        memberships[0].set_quota_limit('vcpu', -1)
        memberships[1].set_quota_limit('vcpu', -1)
        memberships[2].set_quota_limit('vcpu', -1)

        sum_of_quotas = iaas_models.CloudProjectMembership.get_sum_of_quotas_as_dict(
            memberships, quota_names=['vcpu'], fields=['limit'])
        self.assertEqual({'vcpu': -1}, sum_of_quotas)

    def test_set_quota_usage_creates_ancestors_quotas(self):
        membership = iaas_factories.CloudProjectMembershipFactory()

        membership.set_quota_usage('vcpu', 50)

        self.assertEqual(membership.project.quotas.get(name='vcpu').usage, 50)
        self.assertEqual(membership.project.customer.quotas.get(name='vcpu').usage, 50)

    def test_add_quota_usage_affects_ancestors_quotas(self):
        membership1 = iaas_factories.CloudProjectMembershipFactory()
        project = membership1.project
        membership2 = iaas_factories.CloudProjectMembershipFactory(project=project)

        membership1.add_quota_usage('vcpu', 50)
        membership2.add_quota_usage('vcpu', 20)

        self.assertEqual(project.quotas.get(name='vcpu').usage, 70)

    def test_child_quotas_are_created_for_parents_too(self):
        membership = iaas_factories.CloudProjectMembershipFactory()

        self.assertTrue(membership.project.quotas.filter(name='vcpu').exists())

    def test_quotas_are_reseted_on_scope_delete(self):
        membership1 = iaas_factories.CloudProjectMembershipFactory()
        project = membership1.project
        membership2 = iaas_factories.CloudProjectMembershipFactory(project=project)

        membership1.add_quota_usage('vcpu', 50)
        membership2.add_quota_usage('vcpu', 20)
        membership1.delete()

        self.assertEqual(project.quotas.get(name='vcpu').usage, 20)
