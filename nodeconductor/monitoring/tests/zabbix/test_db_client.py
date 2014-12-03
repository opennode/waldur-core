from django.db import DatabaseError
from django.utils import unittest
from mock import Mock

from nodeconductor.monitoring.zabbix.db_client import ZabbixDBClient
from nodeconductor.monitoring.zabbix.errors import ZabbixError


class ZabbixPublicApiTest(unittest.TestCase):

    def setUp(self):
        self.client = ZabbixDBClient()
        self.client.zabbix_api_client.get_host = Mock(return_value={'hostid': 1})

    def test_format_time_and_value_to_segment_list_splits_time_to_segments_right(self):
        start_timestamp = 100
        end_timestamp = 200
        segments_count = 5

        segment_list = self.client.format_time_and_value_to_segment_list(
            [], segments_count, start_timestamp, end_timestamp)

        self.assertEqual(len(segment_list), segments_count)
        step = (end_timestamp - start_timestamp) / segments_count
        for index, segment in enumerate(segment_list):
            self.assertEqual(segment['from'], start_timestamp + step * index)
            self.assertEqual(segment['to'], start_timestamp + step * (index + 1))

    def test_format_time_and_value_to_segment_list_sums_values_in_segments_right(self):
        start_timestamp = 20
        end_timestamp = 60
        segments_count = 2
        first_segment_time_value_list = [(22, 1), (23, 2)]
        second_segment_time_value_list = [(52, 2), (59, 2), (43, 3)]
        time_and_value_list = first_segment_time_value_list + second_segment_time_value_list

        segment_list = self.client.format_time_and_value_to_segment_list(
            time_and_value_list, segments_count, start_timestamp, end_timestamp)

        first_segment, second_segment = segment_list
        expected_first_segment_value = sum([value for _, value in first_segment_time_value_list])
        expected_second_segment_value = sum([value for _, value in second_segment_time_value_list])
        self.assertEqual(first_segment['value'], expected_first_segment_value)
        self.assertEqual(second_segment['value'], expected_second_segment_value)

    def test_get_item_stats_returns_time_segments(self):
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
            {'from': 1415912626L, 'to': 1415912628L, 'value': 2},
            {'from': 1415912628L, 'to': 1415912630L, 'value': 1},
        ]
        self.assertEquals(segment_list, expected_segment_list)
        self.client.zabbix_api_client.get_host.assert_called_once_with(instance)

    def test_get_item_stats_returns_empty_list_on_db_error(self):
        self.client.get_item_time_and_value_list = Mock(side_effect=DatabaseError)

        self.assertEqual(self.client.get_item_stats([], 'cpu', 1, 10, 2), [])
