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


class EventLogFilter(logging.Filter):
    """
    A filter that allows only event records that have event=True as extra parameter.
    """
    def filter(self, record):
        return hasattr(record, 'event')


class EventFormatter(logging.Formatter):

    def format_timestamp(self, time):
        return datetime.utcfromtimestamp(time).isoformat() + 'Z'

    def format(self, record):
        # Create message dict
        message = {
            # TODO: refactor format
            '@timestamp': self.format_timestamp(record.created),
            '@version': 1,
            'message': record.getMessage(),
            'path': record.pathname,

            # Extra Fields
            'levelname': record.levelname,
            'logger': record.name,

            # TODO: example of the expected file - values should come from the record
            "event_type": "vm_instance_start",
            "user_name": record.user.full_name,
            "user_uuid": record.user.uuid.hex,
            "customer_name": "Ministry of Silly Walks",
            "customer_uuid": "167e6162-3b6f-4ae2-a171-2470b63dff00",
            "project_name": "Flying Circus",
            "project_uuid": "267e6162-3b6f-4ae2-a171-2470b63dff00",
            "project_group_name": "Baywatch",
            "project_group_uuid": "78d1ca9377d54aba96bfb5a5c5a8d592",
            "vm_instance_uuid": "78d1ca9377d54aba96bfb5a5c5a8d592",
            "cloud_account_name": "Pythonesque",
            "cloud_account_uuid": "367e6162-3b6f-4ae2-a171-2470b63dff00",
            "@timestamp": "2013-11-05T13:15:30Z",
            "importance": "normal",
            "importance_code": 3,
            "message": "Authenticated user 'geronimo' with full name: Great Geronimo"
        }
        return json.dumps(message)


class TCPEventHandler(SocketHandler, object):
    def __init__(self, host, port):
        super(TCPEventHandler, self).__init__(host, port)
        self.formatter = EventFormatter()

    def makePickle(self, record):
        return self.formatter.format(record) + b'\n'
