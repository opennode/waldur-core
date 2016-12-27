from django.utils import six

from nodeconductor.core.models import User
from nodeconductor.logging.loggers import EventLogger, event_logger
from nodeconductor.structure import models


class CustomerEventLogger(EventLogger):
    customer = models.Customer

    class Meta:
        event_types = ('customer_deletion_succeeded',
                       'customer_update_succeeded',
                       'customer_creation_succeeded')
        event_groups = {
            'customers': event_types,
        }


class BalanceEventLogger(EventLogger):
    customer = models.Customer
    amount = float

    class Meta:
        event_types = ('customer_account_credited',
                       'customer_account_debited')


class ProjectEventLogger(EventLogger):
    project = models.Project
    project_previous_name = six.text_type

    class Meta:
        nullable_fields = ['project_previous_name']
        event_types = ('project_deletion_succeeded',
                       'project_update_succeeded',
                       'project_creation_succeeded',
                       'project_name_update_succeeded')
        event_groups = {
            'projects': event_types,
        }


class CustomerRoleEventLogger(EventLogger):
    customer = models.Customer
    affected_user = User
    structure_type = six.text_type
    role_name = six.text_type

    class Meta:
        event_types = 'role_granted', 'role_revoked'
        event_groups = {
            'customers': event_types,
            'users': event_types,
        }


class ProjectRoleEventLogger(EventLogger):
    project = models.Project
    affected_user = User
    structure_type = six.text_type
    role_name = six.text_type

    class Meta:
        event_types = 'role_granted', 'role_revoked'
        event_groups = {
            'projects': event_types,
            'users': event_types,
        }


class UserOrganizationEventLogger(EventLogger):
    affected_user = User
    affected_organization = six.text_type

    class Meta:
        event_types = ('user_organization_claimed',
                       'user_organization_approved',
                       'user_organization_rejected',
                       'user_organization_removed')


class ResourceEventLogger(EventLogger):
    resource = models.ResourceMixin

    class Meta:
        event_types = (
            'resource_start_scheduled',
            'resource_start_succeeded',
            'resource_start_failed',

            'resource_stop_scheduled',
            'resource_stop_succeeded',
            'resource_stop_failed',

            'resource_restart_scheduled',
            'resource_restart_succeeded',
            'resource_restart_failed',

            'resource_creation_scheduled',
            'resource_creation_succeeded',
            'resource_creation_failed',

            'resource_import_succeeded',
            'resource_update_succeeded',

            'resource_deletion_scheduled',
            'resource_deletion_succeeded',
            'resource_deletion_failed',
        )
        event_groups = {
            'resources': event_types,
        }


event_logger.register('customer_role', CustomerRoleEventLogger)
event_logger.register('project_role', ProjectRoleEventLogger)
event_logger.register('user_organization', UserOrganizationEventLogger)
event_logger.register('customer', CustomerEventLogger)
event_logger.register('project', ProjectEventLogger)
event_logger.register('balance', BalanceEventLogger)
event_logger.register('resource', ResourceEventLogger)
