from __future__ import unicode_literals

import unittest
from datetime import datetime

from django.db import DatabaseError
from mock import Mock, patch

from nodeconductor.core.utils import datetime_to_timestamp
from nodeconductor.monitoring.zabbix.db_client import ZabbixDBClient


class ZabbixPublicApiTest(unittest.TestCase):

    def setUp(self):
        self.client = ZabbixDBClient()

    def test_get_item_stats_returns_time_segments(self):
        self.client.zabbix_api_client.get_host_ids = Mock(return_value=[1])
        self.client.get_item_time_and_value_list = Mock(
            return_value=((1415912625L, 1L), (1415912626L, 1L), (1415912627L, 1L), (1415912628L, 1L)))
        start_timestamp = 1415912624L
        end_timestamp = 1415912630L
        segments_count = 3
        instance = object
        item_key = 'cpu'

        segment_list = self.client.get_item_stats([instance], item_key, start_timestamp, end_timestamp, segments_count)

        expected_segment_list = [
            {'from': 1415912624L, 'to': 1415912626L, 'value': 1},
            {'from': 1415912626L, 'to': 1415912628L, 'value': 1},
            {'from': 1415912628L, 'to': 1415912630L, 'value': 1},
        ]
        self.assertEquals(segment_list, expected_segment_list)
        self.client.zabbix_api_client.get_host_ids.assert_called_once_with([instance])

    def test_get_item_stats_returns_empty_list_on_db_error(self):
        self.client.zabbix_api_client.get_host_ids = Mock(return_value=[])
        self.client.get_item_time_and_value_list = Mock(side_effect=DatabaseError)
        self.assertEqual(self.client.get_item_stats([], 'cpu', 1, 10, 2), [])


class ProjectTimelineStatisticsTest(unittest.TestCase):
    def setUp(self):
        self.client = ZabbixDBClient()

    def test_resource_names_are_converted_values_are_scaled(self):
        hosts = ['a0e2b6c08d474a15b348633a86109933' ]
        items = ['project_storage_limit', 'project_storage_usage']
        start = datetime_to_timestamp(datetime(2015, 6, 9))
        end = datetime_to_timestamp(datetime(2015, 6, 10))
        interval = 'day'

        recordset = [
            (1433808000, 1433894399, 'openstack.project.consumption.gigabytes', 0.0000),
            (1433808000, 1433894399, 'openstack.project.limit.gigabytes', 988972732710.5263),
            (1433894400, 1433980799, 'openstack.project.consumption.gigabytes', 0.0000),
            (1433894400, 1433980799, 'openstack.project.limit.gigabytes', 1073741824000.0000)
        ]

        expected = [
            (1433808000, 1433894399, 'project_storage_usage', 0),
            (1433808000, 1433894399, 'project_storage_limit', 988972732710/1024/1024),
            (1433894400, 1433980799, 'project_storage_usage', 0),
            (1433894400, 1433980799, 'project_storage_limit', 1073741824000/1024/1024)
        ]

        self.client.execute_query = Mock(return_value=recordset)

        with patch('nodeconductor.monitoring.zabbix.sql_utils.get_zabbix_engine', return_value='mysql'):
            actual = self.client.get_projects_quota_timeline(hosts, items, start, end, interval)
            self.client.execute_query.assert_called_once()
            self.assertEqual(expected, actual)
