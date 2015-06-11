from __future__ import unicode_literals

import mock
import unittest
from datetime import datetime
from decimal import Decimal

from django.db import DatabaseError

from nodeconductor.monitoring.zabbix.stats_client import get_stats
from nodeconductor.core.utils import datetime_to_timestamp


class ZabbixStatisticsTest(unittest.TestCase):

    def test_resource_names_are_converted(self):
        hosts = ('a0e2b6c08d474a15b348633a86109933', )
        resources = ('gigabytes', )
        start = datetime_to_timestamp(datetime(2015, 6, 9))
        end = datetime_to_timestamp(datetime(2015, 6, 10))
        interval = 'day'

        recordset = (
            (1433808000, 1433894399, 'openstack.project.consumption.gigabytes', Decimal('0.0000')),
            (1433808000, 1433894399, 'openstack.project.limit.gigabytes', Decimal('988972732710.5263')),
            (1433894400, 1433980799, 'openstack.project.consumption.gigabytes', Decimal('0.0000')),
            (1433894400, 1433980799, 'openstack.project.limit.gigabytes', Decimal('1073741824000.0000'))
        )

        expected = [
            (1433808000, 1433894399, 'gigabytes_usage', 0.0),
            (1433808000, 1433894399, 'gigabytes_limit', 988972732710.5263),
            (1433894400, 1433980799, 'gigabytes_usage', 0.0),
            (1433894400, 1433980799, 'gigabytes_limit', 1073741824000.0)
        ]

        with mock.patch('nodeconductor.monitoring.zabbix.stats_client.execute_query', return_value=recordset):
            actual = get_stats(hosts, resources, start, end, interval)
            self.assertEqual(expected, actual)
