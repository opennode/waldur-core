from django.utils import six

from nodeconductor.core.models import User, SshPublicKey
from nodeconductor.logging.log import EventLogger, event_logger
from nodeconductor.structure import models


class CustomerEventLogger(EventLogger):
    customer = models.Customer

    class Meta:
        event_types = ('customer_deletion_succeeded',
                       'customer_update_succeeded',
                       'customer_creation_succeeded')


class BalanceEventLogger(EventLogger):
    customer = models.Customer
    amount = float

    class Meta:
        event_types = ('customer_account_credited',
                       'customer_account_debited')


class ProjectEventLogger(EventLogger):
    project = models.Project
    project_group = models.ProjectGroup
    project_previous_name = six.text_type

    class Meta:
        nullable_fields = ['project_group', 'project_previous_name']
        event_types = ('project_deletion_succeeded',
                       'project_update_succeeded',
                       'project_creation_succeeded')


class ProjectGroupEventLogger(EventLogger):
    project_group = models.ProjectGroup

    class Meta:
        event_types = ('project_group_deletion_succeeded',
                       'project_group_update_succeeded',
                       'project_group_creation_succeeded')


class CustomerRoleEventLogger(EventLogger):
    customer = models.Customer
    affected_user = User
    structure_type = six.text_type
    role_name = six.text_type

    class Meta:
        event_types = 'role_granted', 'role_revoked'


class ProjectRoleEventLogger(EventLogger):
    project = models.Project
    project_group = models.ProjectGroup
    affected_user = User
    structure_type = six.text_type
    role_name = six.text_type

    class Meta:
        nullable_fields = ['project_group']
        event_types = 'role_granted', 'role_revoked'


class ProjectGroupRoleEventLogger(EventLogger):
    project_group = models.ProjectGroup
    affected_user = User
    structure_type = six.text_type
    role_name = six.text_type

    class Meta:
        event_types = 'role_granted', 'role_revoked'


class ProjectGroupMembershipEventLogger(EventLogger):
    project = models.Project
    project_group = models.ProjectGroup

    class Meta:
        event_types = 'project_added_to_project_group', 'project_removed_from_project_group'


class UserOrganizationEventLogger(EventLogger):
    affected_user = User
    affected_organization = six.text_type

    class Meta:
        event_types = ('user_organization_claimed',
                       'user_organization_approved',
                       'user_organization_rejected',
                       'user_organization_removed')


class ResourceEventLogger(EventLogger):
    resource = models.Resource

    class Meta:
        event_types = ('resource_imported',
                       'resource_created',
                       'resource_deleted')


class ServiceSettingsEventLogger(EventLogger):
    service_settings = models.ServiceSettings
    error_message = six.text_type

    class Meta:
        event_types = ('service_settings_sync_failed',
                       'service_settings_recovered')


class ServiceProjectLinkEventLogger(EventLogger):
    service_project_link = models.ServiceProjectLink
    error_message = six.text_type

    class Meta:
        event_types = ('service_project_link_creation_failed',
                       'service_project_link_sync_failed',
                       'service_project_link_recovered')


class SshSyncEventLogger(EventLogger):
    ssh_key = SshPublicKey
    service_project_link = models.ServiceProjectLink

    class Meta:
        event_types = ('ssh_key_push_succeeded',
                       'ssh_key_push_failed',
                       'ssh_key_remove_succeeded',
                       'ssh_key_remove_failed')


event_logger.register('customer_role', CustomerRoleEventLogger)
event_logger.register('project_role', ProjectRoleEventLogger)
event_logger.register('project_group_role', ProjectGroupRoleEventLogger)
event_logger.register('project_group_membership', ProjectGroupMembershipEventLogger)
event_logger.register('user_organization', UserOrganizationEventLogger)
event_logger.register('customer', CustomerEventLogger)
event_logger.register('project', ProjectEventLogger)
event_logger.register('project_group', ProjectGroupEventLogger)
event_logger.register('balance', BalanceEventLogger)
event_logger.register('resource', ResourceEventLogger)
event_logger.register('service_settings', ServiceSettingsEventLogger)
event_logger.register('service_project_link', ServiceProjectLinkEventLogger)
event_logger.register('ssh_sync', SshSyncEventLogger)
