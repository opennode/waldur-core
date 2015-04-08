from __future__ import unicode_literals

import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import models, transaction
from django.db.models import Q

from nodeconductor.core.log import EventLoggerAdapter
from nodeconductor.quotas import handlers as quotas_handlers
from nodeconductor.structure import signals
from nodeconductor.structure.models import CustomerRole, Project, ProjectRole, ProjectGroupRole, Customer, ProjectGroup


logger = logging.getLogger(__name__)
event_logger = EventLoggerAdapter(logger)


def prevent_non_empty_project_group_deletion(sender, instance, **kwargs):
    related_projects = Project.objects.filter(project_groups=instance)

    if related_projects.exists():
        raise models.ProtectedError(
            "Cannot delete some instances of model 'ProjectGroup' because "
            "they have connected 'Projects'",
            related_projects
        )


def create_project_roles(sender, instance, created, **kwargs):
    if not created:
        return

    with transaction.atomic():
        admin_group = Group.objects.create(name='Role: {0} admin'.format(instance.uuid))
        mgr_group = Group.objects.create(name='Role: {0} mgr'.format(instance.uuid))

        instance.roles.create(role_type=ProjectRole.ADMINISTRATOR, permission_group=admin_group)
        instance.roles.create(role_type=ProjectRole.MANAGER, permission_group=mgr_group)


def create_customer_roles(sender, instance, created, **kwargs):
    if not created:
        return

    with transaction.atomic():
        owner_group = Group.objects.create(name='Role: {0} owner'.format(instance.uuid))

        instance.roles.create(role_type=CustomerRole.OWNER, permission_group=owner_group)


def create_project_group_roles(sender, instance, created, **kwargs):
    if not created:
        return

    with transaction.atomic():
        mgr_group = Group.objects.create(name='Role: {0} group mgr'.format(instance.uuid))
        instance.roles.create(role_type=ProjectGroupRole.MANAGER, permission_group=mgr_group)


def log_customer_save(sender, instance, created=False, **kwargs):
    if created:
        event_logger.info(
            'Customer %s has been created.', instance.name,
            extra={'customer': instance, 'event_type': 'customer_creation_succeeded'})
    else:
        event_logger.info(
            'Customer %s has been updated.', instance.name,
            extra={'customer': instance, 'event_type': 'customer_update_succeeded'})


def log_customer_delete(sender, instance, **kwargs):
    event_logger.info(
        'Customer %s has been deleted.', instance.name,
        extra={'customer': instance, 'event_type': 'customer_deletion_succeeded'})


def log_project_group_save(sender, instance, created=False, **kwargs):
    if created:
        event_logger.info(
            'Project group %s has been created.', instance.name,
            extra={'project_group': instance, 'event_type': 'project_group_creation_succeeded'})
    else:
        event_logger.info(
            'Project group %s has been updated.', instance.name,
            extra={'project_group': instance, 'event_type': 'project_group_update_succeeded'})


def log_project_group_delete(sender, instance, **kwargs):
    event_logger.info(
        'Project group %s has been deleted.', instance.name,
        extra={'project_group': instance, 'event_type': 'project_group_deletion_succeeded'})


def log_project_save(sender, instance, created=False, **kwargs):
    if created:
        event_logger.info(
            'Project %s has been created.', instance.name,
            extra={'project': instance, 'event_type': 'project_creation_succeeded'}
        )
    else:
        event_logger.info(
            'Project %s has been updated.', instance.name,
            extra={'project': instance, 'event_type': 'project_update_succeeded'}
        )


def log_project_delete(sender, instance, **kwargs):
    event_logger.info(
        'Project %s has been deleted.', instance.name,
        extra={'project': instance, 'event_type': 'project_deletion_succeeded'}
    )


change_customer_nc_projects_quota = quotas_handlers.quantity_quota_handler_fabric(
    path_to_quota_scope='customer',
    quota_name='nc-projects',
)


def _get_customer_users(customer):
    return get_user_model().objects.filter(
        Q(groups__customerrole__customer=customer) |
        Q(groups__projectrole__project__customer=customer) |
        Q(groups__projectgrouprole__project_group__customer=customer))


def change_customer_nc_users_quota(sender, structure, user, role, signal, **kwargs):
    """ Modify nc-users quota usage on structure role grant or revoke """
    assert signal in (signals.structure_role_granted, signals.structure_role_revoked), \
        'Handler "change_customer_nc_users_quota" has to be used only with structure_role signals'
    assert sender in (Customer, Project, ProjectGroup), \
        'Handler "change_customer_nc_users_quota" works only with Project, Customer and ProjectGroup models'

    if sender == Customer:
        customer = structure
        customer_users = _get_customer_users(customer).exclude(groups__customerrole__role_type=role)
    elif sender == Project:
        customer = structure.customer
        customer_users = _get_customer_users(customer).exclude(groups__projectrole__role_type=role)
    elif sender == ProjectGroup:
        customer = structure.customer
        customer_users = _get_customer_users(customer).exclude(groups__projectgrouprole__role_type=role)

    if user not in customer_users:
        if signal == signals.structure_role_granted:
            customer.add_quota_usage('nc-users', 1)
        else:
            customer.add_quota_usage('nc-users', -1)
