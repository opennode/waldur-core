from __future__ import unicode_literals

import logging

from django.contrib.auth.models import Group
from django.db import models, transaction

from nodeconductor.core.log import EventLoggerAdapter
from nodeconductor.structure.models import CustomerRole, Project, ProjectRole, ProjectGroupRole


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
            extra={'customer': instance, 'event_type': 'customer_created'})
    else:
        event_logger.info(
            'Customer %s has been updated.', instance.name,
            extra={'customer': instance, 'event_type': 'customer_updated'})


def log_customer_delete(sender, instance, **kwargs):
    event_logger.info(
        'Customer %s has been deleted.', instance.name,
        extra={'customer': instance, 'event_type': 'customer_deleted'})
