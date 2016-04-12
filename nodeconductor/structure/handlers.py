from __future__ import unicode_literals

import logging

from django.conf import settings
from django.db import models, transaction
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model

from nodeconductor.core.tasks import send_task
from nodeconductor.core.models import SshPublicKey, SynchronizationStates
from nodeconductor.structure import SupportedServices, signals
from nodeconductor.structure.log import event_logger
from nodeconductor.structure.managers import filter_queryset_for_user
from nodeconductor.structure.models import (CustomerRole, Project, ProjectRole, ProjectGroupRole,
                                            Customer, ProjectGroup, ServiceProjectLink,
                                            ServiceSettings, Service, Resource)
from nodeconductor.structure.utils import serialize_ssh_key, serialize_user


logger = logging.getLogger(__name__)


def get_links(user=None, project=None):
    if user:
        return [Link(spl)
                for model in ServiceProjectLink.get_all_models()
                for spl in filter_queryset_for_user(model.objects.all(), user)]
    if project:
        return [Link(spl)
                for model in ServiceProjectLink.get_all_models()
                for spl in model.objects.filter(project=project)]
    return []


def get_keys(user=None, project=None):
    if user:
        return SshPublicKey.objects.filter(user=user)
    if project:
        return SshPublicKey.objects.filter(user__groups__projectrole__project=project)
    return []


class Link(object):
    def __init__(self, link):
        self.link = link.to_string()

    def add_user(self, user):
        if not isinstance(user, basestring):
            user = user.uuid.hex
        send_task('structure', 'add_user')(user, self.link)

    def remove_user(self, user):
        send_task('structure', 'remove_user')(serialize_user(user), self.link)

    def add_key(self, key):
        if not isinstance(key, basestring):
            key = key.uuid.hex
        send_task('structure', 'push_ssh_public_key')(key, self.link)

    def remove_key(self, key):
        send_task('structure', 'remove_ssh_public_key')(serialize_ssh_key(key), self.link)


def propagate_new_users_key_to_his_projects_services(sender, instance=None, created=False, **kwargs):
    """ Propagate new ssh public key to all services it belongs via user projects """
    if created:
        for link in get_links(user=instance.user):
            link.add_key(instance)


def remove_stale_users_key_from_his_projects_services(sender, instance=None, **kwargs):
    """ Remove ssh public key from all services it belongs via user projects """
    for link in get_links(user=instance.user):
        link.remove_key(instance)


def propagate_user_to_his_projects_services(sender, instance=None, created=False, **kwargs):
    """ Propagate users involved in the project and their ssh public keys """
    if created:
        link = Link(instance)

        users = get_user_model().objects.filter(groups__projectrole__project=instance.project)
        users = [uuid.hex for uuid in users.values_list('uuid', flat=True)]

        for user in users:
            link.add_user(user)

        for key in get_keys(project=instance.project):
            link.add_key(key)


def remove_stale_user_from_his_projects_services(sender, instance=None, **kwargs):
    """ Remove user from all services it belongs via projects """
    for link in get_links(user=instance):
        link.remove_user(instance)


def propagate_user_to_services_of_newly_granted_project(sender, structure, user, role, **kwargs):
    """ Propagate user and ssh public key to a service of new project """
    keys = get_keys(user=user)

    for link in get_links(project=structure):
        link.add_user(user)

        for key in keys:
            link.add_key(key)


def revoke_roles_on_project_deletion(sender, instance=None, **kwargs):
    instance.remove_all_users()


def remove_stale_user_from_services_of_revoked_project(sender, structure, user, role, **kwargs):
    """ Remove user and ssh public key from a service of old project """
    keys = get_keys(user=user)

    for link in get_links(project=structure):
        link.remove_user(user)

        for key in keys:
            link.remove_key(key)


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
        event_logger.customer.info(
            'Customer {customer_name} has been created.',
            event_type='customer_creation_succeeded',
            event_context={
                'customer': instance,
            })
    else:
        event_logger.customer.info(
            'Customer {customer_name} has been updated.',
            event_type='customer_update_succeeded',
            event_context={
                'customer': instance,
            })


def log_customer_delete(sender, instance, **kwargs):
    event_logger.customer.info(
        'Customer {customer_name} has been deleted.',
        event_type='customer_deletion_succeeded',
        event_context={
            'customer': instance,
        })


def log_customer_account_credited(sender, instance, amount, **kwargs):
    event_logger.balance.info(
        'Balance has been increased by {amount} for customer {customer_name}.',
        event_type='customer_account_credited',
        event_context={
            'customer': instance,
            'amount': amount,
        })


def log_customer_account_debited(sender, instance, amount, **kwargs):
    event_logger.balance.info(
        'Balance has been decreased by {amount} for customer {customer_name}.',
        event_type='customer_account_debited',
        event_context={
            'customer': instance,
            'amount': amount,
        })


def log_project_group_save(sender, instance, created=False, **kwargs):
    if created:
        event_logger.project_group.info(
            'Project group {project_group_name} has been created.',
            event_type='project_group_creation_succeeded',
            event_context={
                'project_group': instance,
            })
    else:
        event_logger.project_group.info(
            'Project group {project_group_name} has been updated.',
            event_type='project_group_update_succeeded',
            event_context={
                'project_group': instance,
            })


def log_project_group_delete(sender, instance, **kwargs):
    event_logger.project_group.info(
        'Project group {project_group_name} has been deleted.',
        event_type='project_group_deletion_succeeded',
        event_context={
            'project_group': instance,
        })


def log_project_save(sender, instance, created=False, **kwargs):
    if created:
        event_logger.project.info(
            'Project {project_name} has been created.',
            event_type='project_creation_succeeded',
            event_context={
                'project': instance,
                'project_group': instance.project_groups.first(),
            })
    else:
        if instance.tracker.has_changed('name'):
            event_logger.project.info(
                'Project has been renamed from {project_previous_name} to {project_name}.',
                event_type='project_name_update_succeeded',
                event_context={
                    'project': instance,
                    'project_group': instance.project_groups.first(),
                    'project_previous_name': instance.tracker.previous('name')
                })
        else:
            event_logger.project.info(
                'Project {project_name} has been updated.',
                event_type='project_update_succeeded',
                event_context={
                    'project': instance,
                    'project_group': instance.project_groups.first()
                })


def log_project_delete(sender, instance, **kwargs):
    event_logger.project.info(
        'Project {project_name} has been deleted.',
        event_type='project_deletion_succeeded',
        event_context={
            'project': instance,
            'project_group': instance.project_groups.first(),
        })


def log_customer_role_granted(sender, structure, user, role, **kwargs):
    event_logger.customer_role.info(
        'User {affected_user_username} has gained role of {role_name} in customer {customer_name}.',
        event_type='role_granted',
        event_context={
            'customer': structure,
            'affected_user': user,
            'structure_type': 'customer',
            'role_name': structure.roles.get(role_type=role).get_role_type_display().lower(),
        })


def log_customer_role_revoked(sender, structure, user, role, **kwargs):
    event_logger.customer_role.info(
        'User {affected_user_username} has lost role of {role_name} in customer {customer_name}.',
        event_type='role_revoked',
        event_context={
            'customer': structure,
            'affected_user': user,
            'structure_type': 'customer',
            'role_name': structure.roles.get(role_type=role).get_role_type_display().lower(),
        })


def log_project_role_granted(sender, structure, user, role, **kwargs):
    event_logger.project_role.info(
        'User {affected_user_username} has gained role of {role_name} in project {project_name}.',
        event_type='role_granted',
        event_context={
            'project': structure,
            'project_group': structure.project_groups.first(),
            'affected_user': user,
            'structure_type': 'project',
            'role_name': structure.roles.get(role_type=role).get_role_type_display().lower(),
        })


def log_project_role_revoked(sender, structure, user, role, **kwargs):
    event_logger.project_role.info(
        'User {affected_user_username} has revoked role of {role_name} in project {project_name}.',
        event_type='role_revoked',
        event_context={
            'project': structure,
            'project_group': structure.project_groups.first(),
            'affected_user': user,
            'structure_type': 'project',
            'role_name': structure.roles.get(role_type=role).get_role_type_display().lower(),
        })


def log_project_group_role_granted(sender, structure, user, role, **kwargs):
    event_logger.project_group_role.info(
        'User {affected_user_username} has gained role of {role_name}'
        ' in project group {project_group_name}.',
        event_type='role_granted',
        event_context={
            'project_group': structure,
            'affected_user': user,
            'structure_type': 'project_group',
            'role_name': structure.roles.get(role_type=role).get_role_type_display().lower(),
        })


def log_project_group_role_revoked(sender, structure, user, role, **kwargs):
    event_logger.project_group_role.info(
        'User {affected_user_username} has gained role of {role_name}'
        ' in project group {project_group_name}.',
        event_type='role_revoked',
        event_context={
            'project_group': structure,
            'affected_user': user,
            'structure_type': 'project_group',
            'role_name': structure.roles.get(role_type=role).get_role_type_display().lower(),
        })


def change_customer_nc_users_quota(sender, structure, user, role, signal, **kwargs):
    """ Modify nc_user_count quota usage on structure role grant or revoke """
    assert signal in (signals.structure_role_granted, signals.structure_role_revoked), \
        'Handler "change_customer_nc_users_quota" has to be used only with structure_role signals'
    assert sender in (Customer, Project, ProjectGroup), \
        'Handler "change_customer_nc_users_quota" works only with Project, Customer and ProjectGroup models'

    if sender == Customer:
        customer = structure
    elif sender in (Project, ProjectGroup):
        customer = structure.customer

    customer_users = customer.get_users()
    customer.set_quota_usage(Customer.Quotas.nc_user_count, customer_users.count())


def log_resource_deleted(sender, instance, **kwargs):
    event_logger.resource.info(
        '{resource_full_name} has been deleted.',
        event_type='resource_deletion_succeeded',
        event_context={'resource': instance})


def log_resource_imported(sender, instance, **kwargs):
    event_logger.resource.info(
        'Resource {resource_full_name} has been imported.',
        event_type='resource_import_succeeded',
        event_context={'resource': instance})


def log_resource_action(sender, instance, name, source, target, **kwargs):
    if source == Resource.States.PROVISIONING:
        if target == Resource.States.ONLINE:
            event_logger.resource.info(
                'Resource {resource_name} has been created.',
                event_type='resource_creation_succeeded',
                event_context={'resource': instance})
        elif target == Resource.States.ERRED:
            event_logger.resource.error(
                'Resource {resource_name} creation has failed.',
                event_type='resource_creation_failed',
                event_context={'resource': instance})
    elif source == Resource.States.STARTING:
        if target == Resource.States.ONLINE:
            event_logger.resource.info(
                'Resource {resource_name} has been started.',
                event_type='resource_start_succeeded',
                event_context={'resource': instance})
        elif target == Resource.States.ERRED:
            event_logger.resource.error(
                'Resource {resource_name} start has failed.',
                event_type='resource_start_failed',
                event_context={'resource': instance})
    elif source == Resource.States.STOPPING:
        if target == Resource.States.OFFLINE:
            event_logger.resource.info(
                'Resource {resource_name} has been stopped.',
                event_type='resource_stop_succeeded',
                event_context={'resource': instance})
        elif target == Resource.States.ERRED:
            event_logger.resource.error(
                'Resource {resource_name} stop has failed.',
                event_type='resource_stop_failed',
                event_context={'resource': instance})
    elif source == Resource.States.RESTARTING:
        if target == Resource.States.ONLINE:
            event_logger.resource.info(
                'Resource {resource_name} has been restarted.',
                event_type='resource_restart_succeeded',
                event_context={'resource': instance})
        elif target == Resource.States.ERRED:
            event_logger.resource.error(
                'Resource {resource_name} restart has failed.',
                event_type='resource_restart_failed',
                event_context={'resource': instance})


def detect_vm_coordinates(sender, instance, name, source, target, **kwargs):
    # Check if geolocation is enabled
    if not settings.NODECONDUCTOR.get('ENABLE_GEOIP', True):
        return

    # VM already has coordinates
    if instance.latitude is not None and instance.longitude is not None:
        return

    if target == Resource.States.ONLINE:
        send_task('structure', 'detect_vm_coordinates')(instance.to_string())


def connect_customer_to_shared_service_settings(sender, instance, created=False, **kwargs):
    if not created:
        return
    customer = instance

    for shared_settings in ServiceSettings.objects.filter(shared=True, state=SynchronizationStates.IN_SYNC):
        try:
            service_model = SupportedServices.get_service_models()[shared_settings.type]['service']
            service_model.objects.create(customer=customer,
                                         settings=shared_settings,
                                         name=shared_settings.name,
                                         available_for_all=True)
        except KeyError:
            logger.warning("Unregistered service of type %s" % shared_settings.type)


def connect_shared_service_settings_to_customers(sender, instance, name, source, target, **kwargs):
    """ Connected service settings with all customers if they were created or become shared """
    service_settings = instance
    if (target != SynchronizationStates.IN_SYNC or
            source not in (SynchronizationStates.ERRED, SynchronizationStates.CREATING) or
            not service_settings.shared):
        return

    service_model = SupportedServices.get_service_models()[service_settings.type]['service']
    for customer in Customer.objects.all():
        if not service_model.objects.filter(customer=customer, settings=service_settings).exists():
            service_model.objects.create(customer=customer,
                                         settings=service_settings,
                                         name=service_settings.name,
                                         available_for_all=True)


def connect_project_to_all_available_services(sender, instance, created=False, **kwargs):
    if not created:
        return
    project = instance

    for service_model in Service.get_all_models():
        for service in service_model.objects.filter(available_for_all=True, customer=project.customer):
            service_project_link_model = service.projects.through
            service_project_link_model.objects.create(project=project, service=service)


def connect_service_to_all_projects_if_it_is_available_for_all(sender, instance, created=False, **kwargs):
    service = instance
    if service.available_for_all:
        service_project_link_model = service.projects.through
        for project in service.customer.projects.all():
            service_project_link_model.objects.get_or_create(project=project, service=service)


def sync_service_settings_with_backend(sender, instance, created=False, **kwargs):
    if not created:
        return

    backend = instance.get_backend()
    if backend.has_global_properties():
        instance.state = SynchronizationStates.IN_SYNC
        instance.save(update_fields=['state'])
        return

    send_task('structure', 'sync_service_settings')(instance.uuid.hex)


def log_service_sync_failed(sender, instance, name, source, target, **kwargs):
    settings = instance
    message = settings.error_message
    if message and target == SynchronizationStates.ERRED:
        logger.error(
            "Service settings %s has failed to sync with an error: %s", settings.uuid.hex, message)


def log_service_recovered(sender, instance, name, source, target, **kwargs):
    settings = instance
    if source == SynchronizationStates.ERRED and target == SynchronizationStates.IN_SYNC:
        logger.info('Service settings %s has been recovered.' % settings)


def delete_service_settings(sender, instance, **kwargs):
    """ Delete not shared service settings without services """
    service = instance
    if not service.settings.shared:
        service.settings.delete()
