from __future__ import unicode_literals

import logging

from django.conf import settings
from django.contrib.auth.models import Group
from django.db import models, transaction
from django.utils import timezone

from nodeconductor.core.tasks import send_task
from nodeconductor.core.models import SynchronizationStates, StateMixin
from nodeconductor.structure import SupportedServices, signals
from nodeconductor.structure.log import event_logger
from nodeconductor.structure.models import (CustomerRole, Project, ProjectRole, ProjectGroupRole,
                                            Customer, ProjectGroup, ServiceSettings, Service, Resource, NewResource)


logger = logging.getLogger(__name__)


def revoke_roles_on_project_deletion(sender, instance=None, **kwargs):
    instance.remove_all_users()


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


def log_resource_creation_succeeded(instance):
    event_logger.resource.info(
        'Resource {resource_name} has been created.',
        event_type='resource_creation_succeeded',
        event_context={'resource': instance})


def log_resource_creation_failed(instance):
    event_logger.resource.error(
        'Resource {resource_name} creation has failed.',
        event_type='resource_creation_failed',
        event_context={'resource': instance})


def log_resource_action(sender, instance, name, source, target, **kwargs):
    if isinstance(instance, StateMixin):
        if source == StateMixin.States.CREATING:
            if target == StateMixin.States.OK:
                log_resource_creation_succeeded(instance)
            elif target == StateMixin.States.ERRED:
                log_resource_creation_failed(instance)
    elif source == Resource.States.PROVISIONING:
        if target == Resource.States.ONLINE:
            log_resource_creation_succeeded(instance)
        elif target == Resource.States.ERRED:
            log_resource_creation_failed(instance)
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

    for shared_settings in ServiceSettings.objects.filter(shared=True):
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


def delete_service_settings_on_service_delete(sender, instance, **kwargs):
    """ Delete not shared service settings without services """
    service = instance
    if not service.settings.shared:
        service.settings.delete()


def init_resource_start_time(sender, instance, name, source, target, **kwargs):
    if (isinstance(instance, Resource) and target == Resource.States.ONLINE) or\
            (isinstance(instance, NewResource) and target == NewResource.States.OK):
        instance.start_time = timezone.now()
        instance.save(update_fields=['start_time'])


def delete_service_settings_on_scope_delete(sender, instance, **kwargs):
    """ If VM that contains service settings were deleted - all settings
        resources could be safely deleted from NC.
    """
    for service_settings in ServiceSettings.objects.filter(scope=instance):
        resource_models = SupportedServices.get_service_name_resources(service_settings.type)
        for resource_model in resource_models:
            resource_model.objects.all().delete()
        service_settings.delete()


def clean_tags_cache_after_tagged_item_saved(sender, instance, **kwargs):
    instance.content_object.clean_tag_cache()


def clean_tags_cache_before_tagged_item_deleted(sender, instance, **kwargs):
    instance.content_object.clean_tag_cache()
