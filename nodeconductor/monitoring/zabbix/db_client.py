import logging
import sys

from django.db import connections, DatabaseError
from django.utils import six

from nodeconductor.core import utils as core_utils
from nodeconductor.monitoring.zabbix import errors, api_client
from nodeconductor.monitoring.zabbix.errors import ZabbixError


logger = logging.getLogger(__name__)


class ZabbixDBClient(object):

    items = {
        'cpu': {'key': 'kvm.vm.cpu.util', 'table': 'history', 'convert_to_mb': False},
        'memory': {'key': 'kvm.vm.memory.size.used', 'table': 'history_uint', 'convert_to_mb': True},
        'storage': {'key': 'kvm.vm.disk.size', 'table': 'history_uint', 'convert_to_mb': True}
    }

    def __init__(self):
        self.zabbix_api_client = api_client.ZabbixApiClient()

    def get_item_stats(self, instances, item, start_timestamp, end_timestamp, segments_count):
        host_ids = []
        for instance in instances:
            try:
                host_ids.append(self.zabbix_api_client.get_host(instance)['hostid'])
            except ZabbixError:
                logger.warn('Failed to get a Zabbix host for instance %s' % instance.uuid)

        # return an empty list if no hosts were found
        if len(host_ids) == 0:
            return []

        item_key = self.items[item]['key']
        item_table = self.items[item]['table']
        convert_to_mb = self.items[item]['convert_to_mb']
        try:
            time_and_value_list = self.get_item_time_and_value_list(
                host_ids, [item_key], item_table, start_timestamp, end_timestamp, convert_to_mb)
            segment_list = core_utils.format_time_and_value_to_segment_list(
                time_and_value_list, segments_count, start_timestamp, end_timestamp, average=True)
            return segment_list
        except DatabaseError as e:
            logger.exception('Can not execute query the Zabbix DB.')
            six.reraise(errors.ZabbixError, e, sys.exc_info()[2])

    def get_item_time_and_value_list(
            self, host_ids, item_keys, item_table, start_timestamp, end_timestamp, convert_to_mb):
        """
        Execute query to zabbix db to get item values from history
        """
        query = (
            'SELECT hi.clock time, (%(value_path)s) value '
            'FROM zabbix.items it JOIN zabbix.%(item_table)s hi on hi.itemid = it.itemid '
            'WHERE it.key_ in (%(item_keys)s) AND it.hostid in (%(host_ids)s) '
            'AND hi.clock < %(end_timestamp)s AND hi.clock >= %(start_timestamp)s '
            'GROUP BY hi.clock '
            'ORDER BY hi.clock'
        )
        parameters = {
            'item_keys': '"' + '", "'.join(item_keys) + '"',
            'start_timestamp': start_timestamp,
            'end_timestamp': end_timestamp,
            'host_ids': ','.join(str(host_id) for host_id in host_ids),
            'item_table': item_table,
            'value_path': 'hi.value' if not convert_to_mb else 'hi.value / (1024*1024)',
        }
        query = query % parameters

        cursor = connections['zabbix'].cursor()
        cursor.execute(query)
        return cursor.fetchall()
