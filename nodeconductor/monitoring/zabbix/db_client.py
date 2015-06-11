from __future__ import unicode_literals

import logging
import sys

from django.db import connections, DatabaseError
from django.utils import six

from nodeconductor.core import utils as core_utils
from nodeconductor.monitoring.zabbix import errors, api_client
from nodeconductor.monitoring.zabbix import sql_utils

logger = logging.getLogger(__name__)


class ZabbixDBClient(object):
    items = {
        'cpu': {
            'key': 'kvm.vm.cpu.util',
            'table': 'history',
            'convert_to_mb': False
        },

        'memory': {
            'key': 'kvm.vm.memory.size.used',
            'table': 'history_uint',
            'convert_to_mb': True
        },

        'storage': {
            'key': 'kvm.vm.disk.size',
            'table': 'history_uint',
            'convert_to_mb': True
        },

        'project_instances_limit': {
            'key': 'openstack.project.quota_limit.instances',
            'table': 'history_uint',
            'convert_to_mb': False
        },

        'project_instances_usage': {
            'key': 'openstack.project.quota_consumption.instances',
            'table': 'history_uint',
            'convert_to_mb': False
        },

        'project_vcpu_limit': {
            'key': 'openstack.project.quota_limit.cores',
            'table': 'history_uint',
            'convert_to_mb': False
        },

        'project_vcpu_usage': {
            'key': 'openstack.project.quota_consumption.cores',
            'table': 'history_uint',
            'convert_to_mb': False
        },

        'project_ram_limit': {
            'key': 'openstack.project.quota_limit.ram',
            'table': 'history_uint',
            'convert_to_mb': True
        },

        'project_ram_usage': {
            'key': 'openstack.project.quota_consumption.ram',
            'table': 'history_uint',
            'convert_to_mb': True
        },

        'project_storage_limit': {
            'key': 'openstack.project.limit.gigabytes',
            'table': 'history_uint',
            'convert_to_mb': True
        },

        'project_storage_usage': {
            'key': 'openstack.project.consumption.gigabytes',
            'table': 'history_uint',
            'convert_to_mb': True
        },
    }

    def __init__(self):
        self.zabbix_api_client = api_client.ZabbixApiClient()

    def get_projects_quota_timeline(self, hosts, items, start, end, interval):
        """
        hosts: list of tenant UUID
        items: list of items, such as 'vcpu', 'ram'
        start, end: timestamp
        interval: day, week, month
        Returns list of tuples like
        (1415912624, 1415912630, 'vcpu_limit', 2048)
        """

        template = r"""
          SELECT {date_span}, item, SUM(value)
            FROM (SELECT {date_trunc} AS date,
                       items.key_ AS item,
                       AVG(value) AS value
                  FROM hosts,
                       items,
                       history_uint
                 WHERE hosts.hostid = items.hostid
                   AND items.itemid = history_uint.itemid
                   AND hosts.name IN ({hosts_placeholder})
                   AND items.key_ IN ({items_placeholder})
                   AND clock >= %s
                   AND clock <= %s
                 GROUP BY date, items.itemid) AS t
          GROUP BY date, item
          """

        try:
            engine = sql_utils.get_zabbix_engine()
            query = template.format(
                date_span=sql_utils.make_date_span(engine, interval, 'date'),
                date_trunc=sql_utils.truncate_date(engine, interval, 'clock'),
                hosts_placeholder=sql_utils.make_list_placeholder(len(hosts)),
                items_placeholder=sql_utils.make_list_placeholder(len(items)),
            )
            items = [self.items[name]['key'] for name in items]
            params = hosts + items + [start, end]
            logging.warning('Prepared Zabbix SQL query for OpenStack projects statistics %s %s', query, params)

            with connections['zabbix'].cursor() as cursor:
                cursor.execute(query, params)
                records = cursor.fetchall()
                logging.debug('Executed Zabbix SQL query for OpenStack projects statistics %s', records)

        except DatabaseError as e:
            logger.exception('Can not execute query the Zabbix DB.')
            six.reraise(errors.ZabbixError, e, sys.exc_info()[2])

        return self.prepare_result(records)

    def prepare_result(self, records):
        """
        Converts names and values
        """
        results = []
        for (start, end, key, value) in records:
            name = self.get_item_name_by_key(key)
            if name == None:
                logging.debug('Invalid item key %s', key)
                continue
            if self.items[name]['convert_to_mb']:
                value = value / (1024 * 1024)
            value = int(value)
            results.append((start, end, name, value))
        return results

    def get_item_name_by_key(self, key):
        for name, value in self.items.items():
            if value['key'] == key:
                return name

    def get_item_stats(self, instances, item, start_timestamp, end_timestamp, segments_count):
        # FIXME: Quick and dirty hack to handle storage in a separate flow
        if item == 'storage':
            return self.get_storage_stats(instances, start_timestamp, end_timestamp, segments_count)

        host_ids = []
        for instance in instances:
            try:
                host_ids.append(self.zabbix_api_client.get_host(instance)['hostid'])
            except errors.ZabbixError:
                logger.warn('Failed to get a Zabbix host for instance %s', instance.uuid)

        # return an empty list if no hosts were found
        if not host_ids:
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

    def get_storage_stats(self, instances, start_timestamp, end_timestamp, segments_count):
        host_ids = []
        for instance in instances:
            try:
                host_data = self.zabbix_api_client.get_host(instance)
                host_ids.append(int(host_data['hostid']))
            except (errors.ZabbixError, ValueError, KeyError):
                logger.warn('Failed to get Zabbix hostid for instance %s', instance.uuid)

        # return an empty list if no hosts were found
        if not host_ids:
            return []

        query = """
            SELECT
              hi.clock - (hi.clock %% 60)               `time`,
              SUM(hi.value) / (1024 * 1024)             `value`
            FROM zabbix.items it
              JOIN zabbix.history_uint hi ON hi.itemid = it.itemid
            WHERE
              it.key_ = 'openstack.vm.disk.size'
              AND
              it.hostid IN %s
              AND
              hi.clock >= %s AND hi.clock < %s
            GROUP BY hi.clock - (hi.clock %% 60)
            ORDER BY hi.clock - (hi.clock %% 60) ASC
        """

        # This is a work-around for MySQL-python<1.2.5
        # that was unable to serialize lists with a single value properly.
        # MySQL-python==1.2.3 is default in Centos 7 as of 2015-03-03.
        if len(host_ids) == 1:
            host_ids.append(host_ids[0])

        parameters = (host_ids, start_timestamp, end_timestamp)

        with connections['zabbix'].cursor() as cursor:
            cursor.execute(query, parameters)
            actual_values = cursor.fetchall()

        # Poor man's resampling
        resampled_values = []
        sampling_step = (end_timestamp - start_timestamp) / segments_count

        for i in range(segments_count):
            segment_start_timestamp = start_timestamp + sampling_step * i
            segment_end_timestamp = segment_start_timestamp + sampling_step

            # Get the closest value that was known before the requested data point
            # This could be written in much more efficient way.
            preceding_values = [
                value for time, value in actual_values
                if time < segment_end_timestamp
                ]
            try:
                value = preceding_values[-1]
            except IndexError:
                value = '0.0000'

            resampled_values.append({
                'from': segment_start_timestamp,
                'to': segment_end_timestamp,
                'value': value,
            })

        return resampled_values
