from __future__ import unicode_literals

import unittest

from django.db import DatabaseError
from mock import Mock

from nodeconductor.monitoring.zabbix.db_client import ZabbixDBClient


class ZabbixPublicApiTest(unittest.TestCase):

    def setUp(self):
        self.client = ZabbixDBClient()

    def test_get_item_stats_returns_time_segments(self):
        self.client.zabbix_api_client.get_host_ids = Mock(return_value=[1])
        start_timestamp = 1415912624L
        end_timestamp = 1415912630L
        time_and_value_list = Mock()
        time_and_value_list.fetchone = Mock(return_value=(1415912630L,1))
        self.client.get_item_time_and_value_list = Mock(return_value=time_and_value_list)
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
