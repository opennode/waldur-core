import logging

from django.db import connections, DatabaseError
from django.conf import settings
from django.utils import six

from nodeconductor.monitoring.zabbix import errors, api_client


logger = logging.getLogger(__name__)


class ZabbixDBClient(object):

    items = {
        'cpu': {'key': 'kvm.vm.cpu.util', 'table': 'history'},
        'memory': {'key': 'kvm.vm.memory.size.used', 'table': 'history_uint'},
        'storage': {'key': 'kvm.vm.disk.size', 'table': 'history_uint'}
    }

    def __init__(self):
        self.zabbix_api_client = api_client.ZabbixApiClient(settings.NODECONDUCTOR['ZABBIX'])

    def get_item_stats(self, instance, item, start_timestamp, end_timestamp, segments_count):
        host_id = self.zabbix_api_client.get_host(instance)['hostid']
        item_key = self.items[item]['key']
        item_table = self.items[item]['table']
        try:
            time_and_value_list = self.get_item_time_and_value_list(
                host_id, [item_key], item_table, start_timestamp, end_timestamp)
            segment_list = self.format_time_and_value_to_segment_list(
                time_and_value_list, segments_count, start_timestamp, end_timestamp)
            return segment_list
        except DatabaseError:
            logger.exception("Can not execute query to zabbix db.")
            six.reraise(errors.ZabbixError, errors.ZabbixError())

    def format_time_and_value_to_segment_list(self, time_and_value_list, segments_count, start_timestamp, end_timestamp):
        """
        Format time_and_value_list to time segments

        Parameters
        ----------
        time_and_value_list: list of tuples
            Have to be sorted by time
            Example: [(time, value), (time, value) ...]
        segments_count: integer
            How many segments will be in result
        Returns
        -------
        List of dictionaries
            Example:
            [{'from': time1, 'to': time2, 'value': sum_of_values_from_time1_to_time2}, ...]
        """
        segment_list = []
        time_step = (end_timestamp - start_timestamp) / segments_count
        for i in range(segments_count):
            segment_start_timestamp = start_timestamp + time_step * i
            segment_end_timestamp = segment_start_timestamp + time_step
            segment_value = sum([
                value for time, value in time_and_value_list
                if time >= segment_start_timestamp and time < segment_end_timestamp])
            segment_list.append({
                'from': segment_start_timestamp,
                'to': segment_end_timestamp,
                'value': segment_value,
            })
        return segment_list

    def get_item_time_and_value_list(self, host_id, item_keys, item_table, start_timestamp, end_timestamp):
        """
        Execute query to zabbix db to get item values from history
        """
        query = (
            'SELECT hi.clock time, hi.value value '
            'FROM zabbix.items it JOIN zabbix.%(item_table)s hi on hi.itemid = it.itemid '
            'WHERE it.key_ in (%(item_keys)s) AND it.hostid = %(host_id)s '
            'AND hi.clock < %(end_timestamp)s  AND hi.clock >= %(start_timestamp)s '
            'GROUP BY hi.clock '
            'ORDER BY hi.clock'
        )
        parametrs = {
            'item_keys': '"' + '", "'.join(item_keys) + '"',
            'start_timestamp': start_timestamp,
            'end_timestamp': end_timestamp,
            'host_id': host_id,
            'item_table': item_table
        }
        query = query % parametrs

        cursor = connections['zabbix'].cursor()
        cursor.execute(query)
        return cursor.fetchall()
