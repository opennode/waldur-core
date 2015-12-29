import random

from django.test import TestCase

from nodeconductor.iaas import models as iaas_models
from nodeconductor.iaas.tests import factories as iaas_factories
from nodeconductor.structure.tests import factories as structure_factories


class QuotaModelMixinTest(TestCase):

    def test_quotas_sum_calculation_if_all_values_are_positive(self):
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

    def test_quotas_sum_calculation_if_some_limit_is_negative(self):
        memberships = iaas_factories.CloudProjectMembershipFactory.create_batch(3)
        memberships[0].set_quota_limit('vcpu', -1)
        memberships[1].set_quota_limit('vcpu', 10)
        memberships[2].set_quota_limit('vcpu', 30)

        sum_of_quotas = iaas_models.CloudProjectMembership.get_sum_of_quotas_as_dict(
            memberships, quota_names=['vcpu'], fields=['limit'])
        self.assertEqual({'vcpu': 40}, sum_of_quotas)

    def test_quotas_sum_calculation_if_all_limits_are_negative(self):
        memberships = iaas_factories.CloudProjectMembershipFactory.create_batch(3)
        memberships[0].set_quota_limit('vcpu', -1)
        memberships[1].set_quota_limit('vcpu', -1)
        memberships[2].set_quota_limit('vcpu', -1)

        sum_of_quotas = iaas_models.CloudProjectMembership.get_sum_of_quotas_as_dict(
            memberships, quota_names=['vcpu'], fields=['limit'])
        self.assertEqual({'vcpu': -1}, sum_of_quotas)

    def test_child_quotas_are_not_created_for_parent_if_they_are_not_defined_in_parents(self):
        membership = iaas_factories.CloudProjectMembershipFactory()

        self.assertFalse(membership.project.quotas.filter(name='vcpu').exists())

    def test_quotas_of_parents_change_on_child_quota_change(self):
        customer = structure_factories.CustomerFactory()
        project1 = structure_factories.ProjectFactory(customer=customer)
        project2 = structure_factories.ProjectFactory(customer=customer)

        project1.set_quota_usage('nc_resource_count', 1)
        project2.set_quota_usage('nc_resource_count', 2)

        self.assertEqual(customer.quotas.get(name='nc_resource_count').usage, 3)

        project1.add_quota_usage('nc_resource_count', 1)
        project2.add_quota_usage('nc_resource_count', -2)

        self.assertEqual(customer.quotas.get(name='nc_resource_count').usage, 2)
