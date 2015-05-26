import json
import uuid
import types
import decimal
import datetime
import logging

from django.apps import apps
from django.utils import six

from nodeconductor.events.middleware import get_current_user


logger = logging.getLogger(__name__)


class EventLoggerError(AttributeError):
    pass


class EventLogger(object):
    """ Base event logger API.
        Fields which must be passed during event log emitting (event context)
        should be defined as attributes for this class in the form of:

        field_name = ObjectClass || '<app_label>.<class_name>'

        A list of supported event types can be defined with help of method get_supported_event_types,
        or 'event_types' property of Meta class. Event type won't be validated if this list is empty.

        Example usage:

        .. code-block:: python

            from nodeconductor.iaas.models import Cloud

            class QuotaEventLogger(EventLogger):
                cloud_account = Cloud
                project = 'structure.Project'
                threshold = float
                quota_type = basestring

                class Meta:
                    event_types = 'quota_threshold_reached',


            quota_logger = QuotaEventLogger(__name__)
            quota_logger.warning(
                '{quota_type} quota threshold has been reached for {project_name}.',
                event_type='quota_threshold_reached',
                event_context=dict(
                    quota_type=quota.name,
                    project=membership.project,
                    cloud_account=membership.cloud,
                    threshold=threshold * quota.limit)
            )
    """

    def __init__(self, logger_name=__name__):
        self._meta = getattr(self, 'Meta', None)
        self.etypes = self.get_supported_event_types()
        self.logger = EventLoggerAdapter(logging.getLogger(logger_name))

    def get_supported_event_types(self):
        return getattr(self._meta, 'event_types', tuple())

    def get_permitted_objects_uuids(self, user):
        permitted_objects_uuids = getattr(self._meta, 'permitted_objects_uuids', None)
        return permitted_objects_uuids(user) if permitted_objects_uuids else {}

    def get_nullable_fields(self):
        return getattr(self._meta, 'nullable_fields', [])

    def info(self, *args, **kwargs):
        self.process('info', *args, **kwargs)

    def error(self, *args, **kwargs):
        self.process('error', *args, **kwargs)

    def warning(self, *args, **kwargs):
        self.process('warning', *args, **kwargs)

    def debug(self, *args, **kwargs):
        self.process('debug', *args, **kwargs)

    def process(self, level, message_template, event_type='undefined', event_context=None):
        if self.etypes and event_type not in self.etypes:
            raise EventLoggerError(
                "Unsupported event type '%s'. Choices are: %s" % (
                    event_type, ', '.join(self.etypes)))

        if not event_context:
            event_context = {}

        context = self.compile_context(**event_context)
        try:
            msg = message_template.format(**context)
        except KeyError as e:
            raise EventLoggerError(
                "Cannot find %s context field. Choices are: %s" % (
                    str(e), ', '.join(context.keys())))

        log = getattr(self.logger, level)
        log(msg, extra={'event_type': event_type, 'event_context': context})

    def compile_context(self, **kwargs):
        # Get a list of fields here in order to be sure all models already loaded.
        if not hasattr(self, 'fields'):
            self.fields = {
                k: apps.get_model(v) if isinstance(v, basestring) else v
                for k, v in self.__class__.__dict__.items()
                if not k.startswith('_') and not isinstance(v, (types.ClassType, types.FunctionType))}

        context = {}
        required_fields = self.fields.copy()

        user = get_current_user()
        user_entity_name = 'user'
        if user and not user.is_anonymous():
            if user_entity_name in required_fields:
                logger.warning(
                    "Event context field '%s' passed directly. "
                    "Currently authenticated user %s ignored." % (
                        user_entity_name, user.username))
            else:
                context.update(user._get_event_log_context(user_entity_name))

        for entity_name, entity in six.iteritems(kwargs):
            if entity_name in required_fields:
                entity_class = required_fields.pop(entity_name)
                if entity is None and entity_name in self.get_nullable_fields():
                    continue
                if not isinstance(entity, entity_class):
                    raise EventLoggerError(
                        "Field '%s' must be an instance of %s but %s received" % (
                            entity_name, entity_class.__name__, entity.__class__.__name__))
            else:
                logger.error(
                    "Field '%s' cannot be used in event context for %s",
                    entity_name, self.__class__.__name__)
                continue

            if isinstance(entity, EventLoggableMixin):
                context.update(entity._get_event_log_context(entity_name))
            elif isinstance(entity, (int, float, basestring, dict, tuple, list, bool)):
                context[entity_name] = entity
            elif entity is None:
                pass
            else:
                context[entity_name] = six.text_type(entity)
                logger.warning(
                    "Cannot properly serialize '%s' context field. "
                    "Must be inherited from EventLoggableMixin." % entity_name)

        if required_fields:
            raise EventLoggerError(
                "Missed fields in event context: %s" % ', '.join(required_fields.keys()))

        return context


class EventLoggableMixin(object):
    """ Mixin to serialize model in event logs.
        Extends django model or custom class with fields extraction method.
    """

    def get_event_log_fields(self):
        return ('uuid', 'name')

    def _get_event_log_context(self, entity_name):
        context = {}
        for field in self.get_event_log_fields():
            if not hasattr(self, field):
                continue

            value = getattr(self, field)

            if isinstance(value, uuid.UUID):
                value = value.hex
            elif isinstance(value, datetime.date):
                value = value.isoformat()
            elif isinstance(value, decimal.Decimal):
                value = float(value)
            else:
                value = six.text_type(value)

            context["{}_{}".format(entity_name, field)] = value

        return context


class EventFormatter(logging.Formatter):

    def format_timestamp(self, time):
        return datetime.datetime.utcfromtimestamp(time).isoformat() + 'Z'

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
        message = {
            # basic
            '@timestamp': self.format_timestamp(record.created),
            '@version': 1,
            'message': record.getMessage(),

            # logging details
            'levelname': record.levelname,
            'logger': record.name,
            'importance': self.levelname_to_importance(record.levelname),
            'importance_code': record.levelno,
        }

        if hasattr(record, 'event_type'):
            message['event_type'] = record.event_type

        if hasattr(record, 'event_context'):
            message.update(record.event_context)

        return json.dumps(message)


class EventLoggerAdapter(logging.LoggerAdapter, object):
    """ LoggerAdapter """

    def __init__(self, logger):
        super(EventLoggerAdapter, self).__init__(logger, {})

    def process(self, msg, kwargs):
        if 'extra' in kwargs:
            kwargs['extra']['event'] = True
        else:
            kwargs['extra'] = {'event': True}
        return msg, kwargs


class RequireEvent(logging.Filter):
    """ A filter that allows only event records. """

    def filter(self, record):
        return getattr(record, 'event', False)


class RequireNotEvent(logging.Filter):
    """ A filter that allows only non-event records. """

    def filter(self, record):
        return not getattr(record, 'event', False)


class TCPEventHandler(logging.handlers.SocketHandler, object):

    def __init__(self, host='localhost', port=5959):
        super(TCPEventHandler, self).__init__(host, int(port))
        self.formatter = EventFormatter()

    def makePickle(self, record):
        return self.formatter.format(record) + b'\n'


class EventLoggerRegistry(object):

    def register(self, name, logger):
        if name in self.__dict__:
            raise EventLoggerError("Logger '%s' already registered." % name)
        self.__dict__[name] = logger() if isinstance(logger, type) else logger

    def get_loggers(self):
        return [l for l in self.__dict__.values() if isinstance(l, EventLogger)]

    def get_permitted_objects_uuids(self, user):
        permitted_objects_uuids = {}
        for elogger in self.get_loggers():
            permitted_objects_uuids.update(elogger.get_permitted_objects_uuids(user))
        return permitted_objects_uuids


# This global object represents the default event logger registry
event_logger = EventLoggerRegistry()
