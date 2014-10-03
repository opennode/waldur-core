from __future__ import absolute_import

import logging


class EventLoggerAdapter(logging.LoggerAdapter):
    """
    LoggerAdapter
    """

    def __init__(self, logger):
        super(EventLoggerAdapter, self).__init__(logger, {})

    def process(self, msg, kwargs):
        kwargs["extra"] = {'event': True}
        return msg, kwargs


class EventLogFilter(logging.Filter):
    """
    A filter that allows only event records that have event=True as extra parameter.
    """
    def filter(self, record):
        if hasattr(record, 'event'):
            return True
        return False