import unittest
import arrow

from django.core.urlresolvers import reverse
from nodeconductor.quotas.serializers import QuotaTimelineStatsSerializer
from rest_framework import test, status
from nodeconductor.quotas.tests.factories import QuotaFactory
from nodeconductor.structure.tests.factories import UserFactory
from nodeconductor.structure.tests.factories import ProjectFactory
from nodeconductor.structure.models import Project
from nodeconductor.quotas.models import QuotaLog

import logging
logger = logging.getLogger(__name__)

class QuotaLogItemTest(test.APITransactionTestCase):
    def test_log_item_created_when_quota_created_or_updated(self):
        quota = QuotaFactory(name='UNIQUE_NAME')
        self.assertEqual(1, quota.items.count(), "Fresh quota has one log item")

        quota.usage = 1
        quota.save()
        self.assertEqual(2, quota.items.count(), "Quota has one log item")

    def test_log_items_are_created_for_project(self):
        project = ProjectFactory()
        self.assertTrue(QuotaLog.objects.for_object(project).count() != 0)


class QuotaTimelineValidationTest(unittest.TestCase):
    def test_valid(self):
        start, end = arrow.now().span('month')
        serializer = QuotaTimelineStatsSerializer(data={
            'scope': 'UUID',
            'from': start.timestamp,
            'to': end.timestamp,
            'interval': 'day'
        })
        self.assertTrue(serializer.is_valid())

    def test_invalid(self):
        serializer = QuotaTimelineStatsSerializer(data={
            'scope': 'UUID',
            'interval': 'INVALID_INTERVAL'
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('interval', serializer.errors)


class QuotaTimelineStatsTest(test.APITransactionTestCase):
    def setUp(self):
        self.interval = 'week'
        self.start, self.end = arrow.now().span(self.interval)
        self.timeframe = {
            'from': self.start.timestamp,
            'to': self.end.timestamp
        }

        self.staff = UserFactory(is_staff=True)
        self.client.force_authenticate(self.staff)

        self.project = ProjectFactory()
        self.quota = QuotaFactory(name='UNIQUE_NAME', scope=self.project)
        QuotaLog.objects.all().delete()

    def test_stats_returns_one_value_for_week_interval(self):
        limit = 100
        usage = 20

        QuotaLog.objects.create(quota=self.quota, created=self.start.datetime, 
            limit=limit, usage=usage)

        data = {
            'scope': self.project.uuid.hex,
            'item': self.quota.name,
            'interval': self.interval
        }
        data.update(self.timeframe)

        response = self.client.get(self.url(), data=data)

        logger.debug(response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(1, len(response.data))

        expected = {
            self.quota.name: limit,
            self.quota.name+'_usage': usage
        }
        expected.update(self.timeframe)
        self.assertEqual(expected, response.data[0])

    def test_stats_returns_7_daily_timeframes_for_week(self):
        points = arrow.Arrow.range('day', self.start, self.end)
        spans = arrow.Arrow.span_range('day', self.start, self.end)
        values = [i*10 for i in range(len(points))]

        QuotaLog.objects.bulk_create([
            QuotaLog(quota=self.quota, created=point.datetime, limit=value) 
            for (point, value) in zip(points, values)
        ])

        expected = []
        for (start, end), value in zip(spans, values):
            expected.append({
                'from': start.timestamp,
                'to': end.timestamp,
                self.quota.name+'_usage': 0.0,
                self.quota.name: value
            })

        data = {
            'scope': self.project.uuid.hex,
            'item': self.quota.name,
            'interval': 'day'
        }
        data.update(self.timeframe)
        response = self.client.get(self.url(), data=data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(points), len(response.data))
        logger.debug(response.data)

        self.assertEqual(expected, response.data)

    def url(self):
        return reverse('stats_quota_timeline')
