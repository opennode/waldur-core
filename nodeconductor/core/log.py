from __future__ import absolute_import, unicode_literals

import json
import logging
from logging.handlers import SocketHandler
from datetime import datetime


class EventLoggerAdapter(logging.LoggerAdapter, object):
    """
    LoggerAdapter
    """

    def __init__(self, logger):
        super(EventLoggerAdapter, self).__init__(logger, {})

    def process(self, msg, kwargs):
        if 'extra' in kwargs:
            kwargs['extra']['event'] = True
        else:
            kwargs['extra'] = {'event': True}
        return msg, kwargs


class RequireEvent(logging.Filter):
    """
    A filter that allows only event records.
    """
    def filter(self, record):
        return hasattr(record, 'event')


class RequireNotEvent(logging.Filter):
    """
    A filter that allows only non-event records.
    """
    def filter(self, record):
        return not getattr(record, 'event', False)


class EventFormatter(logging.Formatter):

    def format_timestamp(self, time):
        return datetime.utcfromtimestamp(time).isoformat() + 'Z'

    def levelname_to_importance(self, levelname):
        if levelname == 'DEBUG':
            return 'low'
        elif levelname == 'INFO':
            return 'normal'
        elif levelname == 'WARNING':
            return 'high'
        elif levelname == 'ERROR':
            return 'very high'
        else:
            return 'critical'

    def get_customer_from_relative(self, *relatives):
        for r in relatives:
            customer = getattr(r, 'customer', None)
            if customer is not None:
                return customer

    def format(self, record):
        # base message
        message = {
            # basic
            '@timestamp': self.format_timestamp(record.created),
            '@version': 1,
            'message': record.getMessage(),
            'path': record.pathname,

            # logging details
            'levelname': record.levelname,
            'logger': record.name,
            'importance': self.levelname_to_importance(record.levelname),
            'importance_code': record.levelno,
            'event_type': getattr(record, 'event_type', 'undefined'),
        }

        # user
        user = getattr(record, 'user', None)
        if user is not None:
            message.update({
                "user_name": getattr(user, 'full_name', ''),
                "user_uuid": str(getattr(user, 'uuid', '')),
            })

        # placeholder for a potential link
        membership = None

        # instance
        instance = getattr(record, 'instance', None)
        if instance is not None:
            membership = getattr(instance, 'cloud_project_membership', None)
            message['vm_instance_uuid'] = str(getattr(instance, 'uuid', ''))

        # project
        project = getattr(record, 'project', None)
        if project is None and membership is not None:
            project = getattr(membership, 'project', None)
            if project is not None:
                message.update({
                    "project_name": getattr(project, 'name', ''),
                    "project_uuid": str(getattr(project, 'uuid', '')),
                })

        # project group
        project_group = getattr(record, 'project_group', None)
        if project_group is not None:
            message.update({
                "project_group_name": getattr(project_group, 'name', ''),
                "project_group_uuid": str(getattr(project_group, 'uuid', '')),
            })

        # cloud
        cloud = getattr(record, 'cloud', None)
        if cloud is None and membership is not None:
            cloud = getattr(membership, 'cloud', None)
            if cloud is not None:
                message.update({
                    "cloud_account_name": getattr(cloud, 'name', ''),
                    "cloud_account_uuid": str(getattr(cloud, 'uuid', '')),
                })

        # customer
        customer = getattr(record, 'customer', None)
        if customer is None:
            customer = self.get_customer_from_relative(project, cloud, project_group)

        if customer is not None:
            message.update({
                "customer_name": getattr(customer, 'name', ''),
                "customer_uuid": str(getattr(customer, 'uuid', '')),
            })

        return json.dumps(message)


class TCPEventHandler(SocketHandler, object):
    def __init__(self, host='localhost', port=5959):
        super(TCPEventHandler, self).__init__(host, port)
        self.formatter = EventFormatter()

    def makePickle(self, record):
        return self.formatter.format(record) + b'\n'
