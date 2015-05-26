from nodeconductor.events.log import EventLogger, event_logger
from nodeconductor.core.models import User


class ProjectEventMixin(object):
    project = 'structure.Project'

    def compile_context(self, **kwargs):
        context = super(ProjectEventMixin, self).compile_context(**kwargs)
        customer = kwargs['project'].customer
        context.update(customer._get_event_log_context('customer'))
        return context


class ProjectGroupEventMixin(object):
    project_group = 'structure.ProjectGroup'

    def compile_context(self, **kwargs):
        context = super(ProjectGroupEventMixin, self).compile_context(**kwargs)
        customer = kwargs['project_group'].customer
        context.update(customer._get_event_log_context('customer'))
        return context


class CustomerEventMixin(object):
    customer = 'structure.Customer'


class RoleEventLogger(EventLogger):
    affected_user = User
    structure_type = basestring
    role_name = basestring

    class Meta:
        event_types = 'role_granted', 'role_revoked'


class CustomerRoleEventLogger(CustomerEventMixin, RoleEventLogger):
    pass


class ProjectRoleEventLogger(ProjectEventMixin, RoleEventLogger):
    pass


class ProjectGroupRoleEventLogger(ProjectGroupEventMixin, RoleEventLogger):
    pass


class ProjectGroupMembershipEventLogger(ProjectGroupEventMixin, EventLogger):
    project = 'structure.Project'

    class Meta:
        event_types = 'project_added_to_project_group', 'project_removed_from_project_group'


event_logger.register('customer_role', CustomerRoleEventLogger)
event_logger.register('project_role', ProjectRoleEventLogger)
event_logger.register('project_group_role', ProjectGroupRoleEventLogger)
event_logger.register('project_group_membership', ProjectGroupMembershipEventLogger)
