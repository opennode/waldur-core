from nodeconductor.logging.log import EventLogger, event_logger
from nodeconductor.core.models import User, SshPublicKey


class AuthEventLogger(EventLogger):
    user = User

    class Meta:
        event_types = ('auth_logged_in_with_username',
                       'auth_logged_in_with_pki',
                       'auth_logged_out')


class UserEventLogger(EventLogger):
    affected_user = User

    class Meta:
        permitted_objects_uuids = staticmethod(lambda user: {'user_uuid': [user.uuid.hex]})
        event_types = ('user_creation_succeeded',
                       'user_update_succeeded',
                       'user_deletion_succeeded',
                       'user_password_updated',
                       'user_activated',
                       'user_deactivated')


class SshPublicKeyEventLogger(EventLogger):
    ssh_key = SshPublicKey

    class Meta:
        event_types = ('ssh_key_creation_succeeded',
                       'ssh_key_deletion_succeeded')


event_logger.register('auth', AuthEventLogger)
event_logger.register('user', UserEventLogger)
event_logger.register('sshkey', SshPublicKeyEventLogger)



# Backward compatibility imports and code
# TODO: remove everything below in flavor of events.log

from datetime import datetime
import logging
import json

from nodeconductor.logging.middleware import get_current_user

from nodeconductor.logging.log import RequireEvent, RequireNotEvent
from nodeconductor.logging.log import TCPEventHandler as NewTCPEventHandler
from nodeconductor.logging.log import EventLoggerAdapter as NewEventLoggerAdapter
from nodeconductor.logging.log import EventFormatter as NewEventFormatter


class EventLoggerAdapter(NewEventLoggerAdapter):

    def process(self, msg, kwargs):
        msg, kwargs = super(EventLoggerAdapter, self).process(msg, kwargs)
        kwargs['extra']['_old_type_event'] = True
        return msg, kwargs


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
        self.add_related_details(message, user, 'user',
                                 'username', 'full_name', 'native_name')

        # affected user
        affected_user = self.get_related('affected_user', record)
        self.add_related_details(message, affected_user, 'affected_user',
                                 'username', 'full_name', 'native_name')

        try:
            message['affected_organization'] = record.affected_organization
        except AttributeError:
            pass

        # FIXME: this horribly introduces cyclic dependencies,
        # remove after logging refactoring
        def extract_instance(source_name):
            from django.core.exceptions import ObjectDoesNotExist
            from nodeconductor.iaas.models import Instance

            source = self.get_related(source_name, record)
            if source is None:
                return None

            try:
                instance = source.backup_source
            except ObjectDoesNotExist:
                return None

            if not isinstance(instance, Instance):
                return None

            return instance

        # instance
        instance = self.get_related(
            'instance', record,
            lambda _: extract_instance('backup'),
            lambda _: extract_instance('backup_schedule'),
        )
        self.add_related_details(message, instance, 'iaas_instance', 'name')

        if hasattr(record, 'instance_id'):
            message['iaas_instance_uuid'] = record.instance_id

        # flavor
        flavor = self.get_related('flavor', instance)
        self.add_related_details(message, flavor, 'iaas_instance_flavor', 'name', 'cores', 'ram', 'disk')

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

        # adding/removing roles
        try:
            structure_type = getattr(record, 'structure_type')
            role_name = getattr(record, 'role_name')
        except AttributeError:
            pass
        else:
            message['structure_type'] = structure_type
            message['role_name'] = role_name

        return json.dumps(message)

    def get_related(self, related_name, *sources):
        for source in sources:
            try:
                if callable(source):
                    result = source(related_name)
                else:
                    result = getattr(source, related_name)

                if result is not None:
                    return result
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


class TCPEventHandler(NewTCPEventHandler):
    def makePickle(self, record):
        old = getattr(record, '_old_type_event', False)
        cls = EventFormatter() if old else NewEventFormatter()
        return cls.format(record) + b'\n'
