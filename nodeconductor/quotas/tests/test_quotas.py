from datetime import timedelta

from django.utils import timezone
from rest_framework import test, status
from reversion import revisions as reversion

from nodeconductor.core import utils as core_utils
from nodeconductor.quotas.tests import factories
from nodeconductor.structure import models as structure_models
from nodeconductor.structure.tests import factories as structure_factories


class QuotaHistoryTest(test.APITransactionTestCase):

    def setUp(self):
        self.customer = structure_factories.CustomerFactory()
        self.owner = structure_factories.UserFactory(username='owner')
        self.customer.add_user(self.owner, structure_models.CustomerRole.OWNER)

        self.quota = factories.QuotaFactory(scope=self.customer)
        self.url = factories.QuotaFactory.get_url(self.quota, 'history')
        # Hook for test: lets say that revision was created one hour ago
        version = reversion.get_for_date(self.quota, timezone.now())
        version.revision.date_created = timezone.now() - timedelta(hours=1)
        version.revision.save()

    def test_old_version_of_quota_is_available(self):
        old_usage = self.quota.usage
        self.quota.usage = self.quota.usage + 1
        self.quota.save()
        history_timestamp = core_utils.datetime_to_timestamp(timezone.now() - timedelta(minutes=30))

        self.client.force_authenticate(self.owner)
        response = self.client.get(self.url, data={'point': history_timestamp})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]['point'], history_timestamp)
        self.assertEqual(response.data[0]['object']['usage'], old_usage)

    def test_endpoint_does_not_return_object_if_date(self):
        history_timestamp = core_utils.datetime_to_timestamp(timezone.now() - timedelta(hours=2))

        self.client.force_authenticate(self.owner)
        response = self.client.get(self.url, data={'point': history_timestamp})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn('object', response.data[0])

    def test_timeinterval_is_splitted_equal_parts(self):
        start_timestamp = 1436094000
        end_timestamp = 1436096000

        self.client.force_authenticate(self.owner)
        response = self.client.get(self.url, data={'points_count': 3, 'start': start_timestamp, 'end': end_timestamp})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]['point'], start_timestamp)
        self.assertEqual(response.data[1]['point'], start_timestamp + (end_timestamp - start_timestamp) / 2)
        self.assertEqual(response.data[2]['point'], end_timestamp)


# TODO: add CRUD tests for quota endpoint.
