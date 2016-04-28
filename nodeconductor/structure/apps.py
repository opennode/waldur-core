from __future__ import unicode_literals

from django.apps import AppConfig
from django.contrib.auth import get_user_model
from django.db.models import signals
from django_fsm import signals as fsm_signals


class StructureConfig(AppConfig):
    name = 'nodeconductor.structure'
    verbose_name = 'Structure'

    def ready(self):
        from nodeconductor.core.models import SshPublicKey, CoordinatesMixin
        from nodeconductor.structure.models import Resource, ServiceProjectLink, Service, set_permissions_for_model
        from nodeconductor.structure import handlers
        from nodeconductor.structure import signals as structure_signals

        User = get_user_model()
        Customer = self.get_model('Customer')
        Project = self.get_model('Project')
        ProjectGroup = self.get_model('ProjectGroup')

        signals.post_save.connect(
            handlers.log_customer_save,
            sender=Customer,
            dispatch_uid='nodeconductor.structure.handlers.log_customer_save',
        )

        signals.post_delete.connect(
            handlers.log_customer_delete,
            sender=Customer,
            dispatch_uid='nodeconductor.structure.handlers.log_customer_delete',
        )

        signals.post_save.connect(
            handlers.create_customer_roles,
            sender=Customer,
            dispatch_uid='nodeconductor.structure.handlers.create_customer_roles',
        )

        signals.post_save.connect(
            handlers.create_project_roles,
            sender=Project,
            dispatch_uid='nodeconductor.structure.handlers.create_project_roles',
        )

        signals.post_save.connect(
            handlers.log_project_save,
            sender=Project,
            dispatch_uid='nodeconductor.structure.handlers.log_project_save',
        )

        signals.post_delete.connect(
            handlers.log_project_delete,
            sender=Project,
            dispatch_uid='nodeconductor.structure.handlers.log_project_delete',
        )

        signals.post_save.connect(
            handlers.create_project_group_roles,
            sender=ProjectGroup,
            dispatch_uid='nodeconductor.structure.handlers.create_project_group_roles',
        )

        signals.pre_delete.connect(
            handlers.prevent_non_empty_project_group_deletion,
            sender=ProjectGroup,
            dispatch_uid='nodeconductor.structure.handlers.prevent_non_empty_project_group_deletion',
        )

        signals.post_save.connect(
            handlers.log_project_group_save,
            sender=ProjectGroup,
            dispatch_uid='nodeconductor.structure.handlers.log_project_group_save',
        )

        signals.post_delete.connect(
            handlers.log_project_group_delete,
            sender=ProjectGroup,
            dispatch_uid='nodeconductor.structure.handlers.log_project_group_delete',
        )

        set_permissions_for_model(
            User.groups.through,
            customer_path='group__projectrole__project__customer',
            project_group_path='group__projectrole__project__project_groups',
            project_path='group__projectrole__project',
        )

        set_permissions_for_model(
            ProjectGroup.projects.through,
            customer_path='projectgroup__customer',
        )

        # increase nc_user_count quota usage on adding user to customer
        structure_models_with_roles = (Customer, Project, ProjectGroup)
        for model in structure_models_with_roles:
            name = 'increase_customer_nc_users_quota_on_adding_user_to_%s' % model.__name__
            structure_signals.structure_role_granted.connect(
                handlers.change_customer_nc_users_quota,
                sender=model,
                dispatch_uid='nodeconductor.structure.handlers.%s' % name,
            )

        # decrease nc_user_count quota usage on removing user from customer
        for model in structure_models_with_roles:
            name = 'decrease_customer_nc_users_quota_on_adding_user_to_%s' % model.__name__
            structure_signals.structure_role_revoked.connect(
                handlers.change_customer_nc_users_quota,
                sender=model,
                dispatch_uid='nodeconductor.structure.handlers.%s' % name,
            )

        structure_signals.structure_role_granted.connect(
            handlers.log_customer_role_granted,
            sender=Customer,
            dispatch_uid='nodeconductor.structure.handlers.log_customer_role_granted',
        )

        structure_signals.structure_role_revoked.connect(
            handlers.log_customer_role_revoked,
            sender=Customer,
            dispatch_uid='nodeconductor.structure.handlers.log_customer_role_revoked',
        )

        structure_signals.structure_role_granted.connect(
            handlers.log_project_role_granted,
            sender=Project,
            dispatch_uid='nodeconductor.structure.handlers.log_project_role_granted',
        )

        structure_signals.structure_role_revoked.connect(
            handlers.log_project_role_revoked,
            sender=Project,
            dispatch_uid='nodeconductor.structure.handlers.log_project_role_revoked',
        )

        structure_signals.structure_role_granted.connect(
            handlers.log_project_group_role_granted,
            sender=ProjectGroup,
            dispatch_uid='nodeconductor.structure.handlers.log_project_group_role_granted',
        )

        structure_signals.structure_role_revoked.connect(
            handlers.log_project_group_role_revoked,
            sender=ProjectGroup,
            dispatch_uid='nodeconductor.structure.handlers.log_project_group_role_revoked',
        )

        for index, model in enumerate(Resource.get_all_models()):
            signals.post_delete.connect(
                handlers.log_resource_deleted,
                sender=model,
                dispatch_uid='nodeconductor.structure.handlers.log_resource_deleted_{}_{}'.format(
                    model.__name__, index),
            )

            structure_signals.resource_imported.connect(
                handlers.log_resource_imported,
                sender=model,
                dispatch_uid='nodeconductor.structure.handlers.log_resource_imported_{}_{}'.format(
                    model.__name__, index),
            )

            fsm_signals.post_transition.connect(
                handlers.log_resource_action,
                sender=model,
                dispatch_uid='nodeconductor.structure.handlers.log_resource_action_{}_{}'.format(
                    model.__name__, index),
            )

            fsm_signals.post_transition.connect(
                handlers.init_resource_start_time,
                sender=model,
                dispatch_uid='nodeconductor.structure.handlers.init_resource_start_time_{}_{}'.format(
                    model.__name__, index),
            )

            signals.pre_delete.connect(
                handlers.delete_service_settings_on_scope_delete,
                sender=model,
                dispatch_uid='nodeconductor.structure.handlers.delete_service_settings_on_scope_delete_{}_{}'.format(
                    model.__name__, index),
            )

        for index, model in enumerate(Resource.get_vm_models()):
            if issubclass(model, CoordinatesMixin):
                fsm_signals.post_transition.connect(
                    handlers.detect_vm_coordinates,
                    sender=model,
                    dispatch_uid='nodeconductor.structure.handlers.detect_vm_coordinates_{}_{}'.format(
                        model.__name__, index),
                )

        for model in ServiceProjectLink.get_all_models():
            name = 'propagate_ssh_keys_for_%s' % model.__name__
            signals.post_save.connect(
                handlers.propagate_user_to_his_projects_services,
                sender=model,
                dispatch_uid='nodeconductor.structure.handlers.%s' % name,
            )

        signals.pre_delete.connect(
            handlers.remove_stale_user_from_his_projects_services,
            sender=User,
            dispatch_uid='nodeconductor.structure.handlers.remove_stale_user_from_his_projects_services',
        )

        signals.post_save.connect(
            handlers.propagate_new_users_key_to_his_projects_services,
            sender=SshPublicKey,
            dispatch_uid='nodeconductor.structure.handlers.propagate_new_users_key_to_his_projects_services',
        )

        signals.post_delete.connect(
            handlers.remove_stale_users_key_from_his_projects_services,
            sender=SshPublicKey,
            dispatch_uid='nodeconductor.structure.handlers.remove_stale_users_key_from_his_projects_services',
        )

        signals.pre_delete.connect(
            handlers.revoke_roles_on_project_deletion,
            sender=Project,
            dispatch_uid='nodeconductor.structure.handlers.revoke_roles_on_project_deletion',
        )

        structure_signals.structure_role_granted.connect(
            handlers.propagate_user_to_services_of_newly_granted_project,
            sender=Project,
            dispatch_uid='nodeconductor.structure.handlers.propagate_user_to_services_of_newly_granted_project',
        )

        structure_signals.structure_role_revoked.connect(
            handlers.remove_stale_user_from_services_of_revoked_project,
            sender=Project,
            dispatch_uid='nodeconductor.structure.handlers.remove_stale_user_from_services_of_revoked_project',
        )

        structure_signals.customer_account_credited.connect(
            handlers.log_customer_account_credited,
            sender=Customer,
            dispatch_uid='nodeconductor.structure.handlers.log_customer_account_credited',
        )

        structure_signals.customer_account_debited.connect(
            handlers.log_customer_account_debited,
            sender=Customer,
            dispatch_uid='nodeconductor.structure.handlers.log_customer_account_debited',
        )

        signals.post_save.connect(
            handlers.connect_customer_to_shared_service_settings,
            sender=Customer,
            dispatch_uid='nodeconductor.structure.handlers.connect_customer_to_shared_service_settings',
        )

        signals.post_save.connect(
            handlers.connect_project_to_all_available_services,
            sender=Project,
            dispatch_uid='nodeconductor.structure.handlers.connect_project_to_all_available_services',
        )

        for index, service_model in enumerate(Service.get_all_models()):
            signals.post_save.connect(
                handlers.connect_service_to_all_projects_if_it_is_available_for_all,
                sender=service_model,
                dispatch_uid='nodeconductor.structure.handlers.'
                             'connect_service_{}_to_all_projects_if_it_is_available_for_all_{}'.format(
                                 service_model.__name__, index),
            )

            signals.post_delete.connect(
                handlers.delete_service_settings_on_service_delete,
                sender=service_model,
                dispatch_uid='nodeconductor.structure.handlers.delete_service_settings_on_service_delete_{}_{}'.format(
                    service_model.__name__, index),
            )
