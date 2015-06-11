from __future__ import unicode_literals

import mock
import unittest
from datetime import datetime
from decimal import Decimal

from django.db import DatabaseError

from nodeconductor.monitoring.zabbix.db_client import ZabbixDBClient
from nodeconductor.core.utils import datetime_to_timestamp


class ZabbixStatisticsTest(unittest.TestCase):

    def test_resource_names_are_converted_values_are_scaled(self):
        hosts = ('a0e2b6c08d474a15b348633a86109933', )
        resources = ('storage', )
        items = set([
            'openstack.project.limit.gigabytes',
            'openstack.project.consumption.gigabytes'
        ])
        start = datetime_to_timestamp(datetime(2015, 6, 9))
        end = datetime_to_timestamp(datetime(2015, 6, 10))
        interval = 'day'

        recordset = [
            (1433808000, 1433894399, 'openstack.project.consumption.gigabytes', Decimal('0.0000')),
            (1433808000, 1433894399, 'openstack.project.limit.gigabytes', Decimal('988972732710.5263')),
            (1433894400, 1433980799, 'openstack.project.consumption.gigabytes', Decimal('0.0000')),
            (1433894400, 1433980799, 'openstack.project.limit.gigabytes', Decimal('1073741824000.0000'))
        ]

        expected = [
            (1433808000, 1433894399, 'storage_usage', 0),
            (1433808000, 1433894399, 'storage_limit', 988972732710/1024/1024),
            (1433894400, 1433980799, 'storage_usage', 0),
            (1433894400, 1433980799, 'storage_limit', 1073741824000/1024/1024)
        ]

        with mock.patch('nodeconductor.monitoring.zabbix.db_client.ProjectsQuotaTimeline.fetch_data', 
            return_value=recordset) as fetch_data:
            actual = ZabbixDBClient().get_projects_quota_timeline(hosts, resources, start, end, interval)
            fetch_data.assert_called_once()
            self.assertEqual(expected, actual)
