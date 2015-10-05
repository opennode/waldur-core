from __future__ import unicode_literals

import unittest

from django.db import DatabaseError
from mock import Mock

from nodeconductor.monitoring.zabbix.db_client import ZabbixDBClient


class ZabbixPublicApiTest(unittest.TestCase):

    def setUp(self):
        self.client = ZabbixDBClient()

    def test_get_item_stats_returns_empty_list_on_db_error(self):
        self.client.zabbix_api_client.get_host_ids = Mock(return_value=[])
        self.client.get_item_time_and_value_list = Mock(side_effect=DatabaseError)
        self.assertEqual(self.client.get_item_stats([], 'cpu', 1, 10, 2), [])
