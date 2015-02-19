from __future__ import absolute_import, unicode_literals

from datetime import datetime
import logging
from logging.handlers import SocketHandler
import json

from nodeconductor.core.middleware import get_current_user


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
        return getattr(record, 'event', False)


class RequireNotEvent(logging.Filter):
    """
    A filter that allows only non-event records.
    """
    def filter(self, record):
        return not getattr(record, 'event', False)


# FIXME: Move out of core since it contains too much downstream specifics
# noinspection PyMethodMayBeStatic
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
        user = self.get_related('user', record, lambda _: get_current_user())
        self.add_related_details(message, user, 'user', 'username')

        # affected user
        affected_user = self.get_related('affected_user', record)
        self.add_related_details(message, affected_user, 'affected_user', 'username')

        # instance
        instance = self.get_related('instance', record)
        self.add_related_details(message, instance, 'iaas_instance', 'hostname')

        # cloud project membership
        membership = self.get_related('cloud_project_membership', instance)

        # project
        project = self.get_related('project', record, membership)
        self.add_related_details(message, project, 'project')

        # project group
        project_group = self.get_related('project_group', record,
                                         lambda _: project and project.project_groups.first())
        self.add_related_details(message, project_group, 'project_group')

        # cloud
        cloud = self.get_related('cloud', record, membership)
        self.add_related_details(message, cloud, 'cloud_account')

        # customer
        customer = self.get_related('customer', record, project, cloud, project_group)
        self.add_related_details(message, customer, 'customer',
            'name', 'abbreviation', 'contact_details')

        return json.dumps(message)

    def get_related(self, related_name, *sources):
        for source in sources:
            try:
                if callable(source):
                    return source(related_name)
                return getattr(source, related_name)
            except (AttributeError, TypeError):
                pass

        return None

    def add_related_details(self, message, related, related_name, *name_attrs):
        if related is None:
            return

        if not name_attrs:
            name_attrs = ('name',)

        # This way we don't rely on the model field "hyphenated" setting
        # and always log UUID without hyphens
        try:
            related_uuid = related.uuid.hex
        except AttributeError:
            related_uuid = ''

        message["{0}_uuid".format(related_name)] = related_uuid
        for name_attr in name_attrs:
            message["{0}_{1}".format(related_name, name_attr)] = getattr(related, name_attr, '')


class TCPEventHandler(SocketHandler, object):
    def __init__(self, host='localhost', port=5959):
        super(TCPEventHandler, self).__init__(host, port)
        self.formatter = EventFormatter()

    def makePickle(self, record):
        return self.formatter.format(record) + b'\n'
