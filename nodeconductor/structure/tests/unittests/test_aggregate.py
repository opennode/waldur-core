import random

from django.test import TestCase

from nodeconductor.openstack import models as openstack_models
from nodeconductor.openstack.tests import factories as openstack_factories


class QuotaModelMixinTest(TestCase):

    def test_quotas_sum_calculation_if_all_values_are_positive(self):
        # We have 3 links
        links = openstack_factories.OpenStackServiceProjectLinkFactory.create_batch(3)
        model = openstack_models.OpenStackServiceProjectLink

        # Each link has non-zero quotas
        for link in links:
            for quota_name in link.QUOTAS_NAMES:
                limit = random.choice([10, 20, 30, 40])
                link.set_quota_limit(quota_name, limit)
                link.set_quota_usage(quota_name, limit / 2)

        qs = model.objects.all()
        sum_of_quotas = model.get_sum_of_quotas_for_querysets([qs])

        expected = {}
        for quota_name in model.QUOTAS_NAMES:
            expected[quota_name] = sum(
                link.quotas.get(name=quota_name).limit for link in links)
            expected[quota_name + '_usage'] = sum(
                link.quotas.get(name=quota_name).usage for link in links)

        self.assertEqual(expected, sum_of_quotas)
