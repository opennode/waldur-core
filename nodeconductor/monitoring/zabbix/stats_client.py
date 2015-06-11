from __future__ import unicode_literals

import sys
import logging

from django.db import connections, DatabaseError, NotSupportedError
from django.conf import settings
from django.utils import six

from nodeconductor.monitoring.zabbix import errors
from nodeconductor.monitoring.zabbix.utils import ItemsNames
from nodeconductor.monitoring.zabbix.sql_utils import make_list_placeholder, sql_date_span, sql_truncate_date

logger = logging.getLogger(__name__)


def get_stats(hosts, resources, start, end, interval):
    names = ItemsNames()
    items = names.get_items(resources)

    records = execute_query(hosts, items, start, end, interval)

    return [(start, end, names.get_label(item), float(value))
            for (start, end, item, value) in records]


def execute_query(hosts, items, start, end, interval):
    """
    hosts: list of tenant UUID
    items: list of items, such as 'openstack.project.limit.gigabytes'
    start, end: timestamp
    interval: day, week, month
    Returns list of tuples like
    (1415912624, 1415912630, 'openstack.project.limit.gigabytes', 2048.0)
    """

    try:
        query = prepare_sql(hosts, items, start, end, interval)
        logging.debug('Prepared Zabbix SQL query for OpenStack projects statistics %s', query)

        with connections['zabbix'].cursor() as cursor:
            cursor.execute(query, list(hosts) + list(items))
            records = cursor.fetchall()

            logging.debug('Executed Zabbix SQL query for OpenStack projects statistics %s', records)
            return records

    except DatabaseError as e:
        logger.exception('Can not execute query the Zabbix DB.')
        six.reraise(errors.ZabbixError, e, sys.exc_info()[2])


def prepare_sql(hosts, items, start, end, interval):
    template = """
  SELECT {date_span}, item, sum(value)
    FROM (SELECT {date_trunc} AS date,
               items.key_ AS item,
               avg(value) AS value
          FROM hosts, 
               items,
               history_uint
         WHERE hosts.hostid = items.hostid
           AND items.itemid = history_uint.itemid
           AND hosts.name IN ({hosts})
           AND items.key_ IN ({items})
           AND clock >= {start}
           AND clock <= {end}
         GROUP BY date, items.itemid) AS t
  GROUP BY date, item
  """
    engine = get_zabbix_engine()
    query = template.format(
        date_span=sql_date_span(engine, interval, 'date'),
        date_trunc=sql_truncate_date(engine, interval, 'clock'),
        hosts=make_list_placeholder(hosts),
        items=make_list_placeholder(items),
        start=start,
        end=end
    )
    return query


def get_zabbix_engine():
    cls_name = settings.DATABASES['zabbix']['ENGINE']

    for engine in ('mysql', 'postgresql'):
        if engine in cls_name:
            return engine
    raise NotSupportedError("Database engine %s is not supported" % engine)
