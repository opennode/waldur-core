from __future__ import absolute_import, unicode_literals

import logging


class EventLoggerAdapter(logging.LoggerAdapter, object):
    """
    LoggerAdapter
    """

    def __init__(self, logger):
        super(EventLoggerAdapter, self).__init__(logger, {})

    def process(self, msg, kwargs):
        kwargs['extra'] = {'event': True}
        return msg, kwargs


class EventLogFilter(logging.Filter):
    """
    A filter that allows only event records that have event=True as extra parameter.
    """
    def filter(self, record):
        return hasattr(record, 'event')