import random

from django.test import TestCase

from nodeconductor.iaas import models as iaas_models
from nodeconductor.iaas.tests import factories as iaas_factories


class QuotaModelMixinTest(TestCase):

    def setUp(self):
        # we have 3 memberships:
        self.memberships = iaas_factories.CloudProjectMembershipFactory.create_batch(3)
        # each membership has non zero quotas:
        for membership in self.memberships:
            for quota_name in membership.QUOTAS_NAMES:
                limit = random.choice([10, 20, 30, 40])
                membership.set_quota_limit(quota_name, limit)
                membership.set_quota_usage(quota_name, limit / 2)

    def test_get_sum_of_quotas_as_dict_return_sum_of_all_quotas(self):
        owners = self.memberships[:2]

        sum_of_quotas = iaas_models.CloudProjectMembership.get_sum_of_quotas_as_dict(owners)

        expected_sum_of_quotas = {}
        for quota_name in iaas_models.CloudProjectMembership.QUOTAS_NAMES:
            expected_sum_of_quotas[quota_name] = sum(owner.quotas.get(name=quota_name).limit for owner in owners)
            expected_sum_of_quotas[quota_name + '_usage'] = sum(
                owner.quotas.get(name=quota_name).usage for owner in owners)

        self.assertEqual(expected_sum_of_quotas, sum_of_quotas)
