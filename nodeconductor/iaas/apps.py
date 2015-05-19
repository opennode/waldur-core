from __future__ import unicode_literals

from django.apps import AppConfig
from django.db.models import signals

from nodeconductor.core import handlers as core_handlers
from nodeconductor.core.models import SshPublicKey
from nodeconductor.core.signals import pre_serializer_fields
from nodeconductor.iaas import handlers
from nodeconductor.quotas import handlers as quotas_handlers
from nodeconductor.structure.models import Project
from nodeconductor.structure.signals import structure_role_granted, structure_role_revoked


class IaasConfig(AppConfig):
    name = 'nodeconductor.iaas'
    verbose_name = "NodeConductor IaaS"

    # See, https://docs.djangoproject.com/en/1.7/ref/applications/#django.apps.AppConfig.ready
    def ready(self):
        Instance = self.get_model('Instance')
        CloudProjectMembership = self.get_model('CloudProjectMembership')

        from nodeconductor.structure.serializers import CustomerSerializer, ProjectSerializer

        signals.post_migrate.connect(handlers.sync_openstack_settings, sender=self)

        pre_serializer_fields.connect(
            handlers.add_clouds_to_related_model,
            sender=CustomerSerializer,
            dispatch_uid='nodeconductor.iaas.handlers.add_clouds_to_customer',
        )

        pre_serializer_fields.connect(
            handlers.add_clouds_to_related_model,
            sender=ProjectSerializer,
            dispatch_uid='nodeconductor.iaas.handlers.add_clouds_to_project',
        )

        signals.post_save.connect(
            handlers.propagate_new_users_key_to_his_projects_clouds,
            sender=SshPublicKey,
            dispatch_uid='nodeconductor.iaas.handlers.propagate_new_users_key_to_his_projects_clouds',
        )

        signals.post_delete.connect(
            handlers.remove_stale_users_key_from_his_projects_clouds,
            sender=SshPublicKey,
            dispatch_uid='nodeconductor.iaas.handlers.remove_stale_key_from_his_projects_clouds',
        )

        structure_role_granted.connect(
            handlers.propagate_users_keys_to_clouds_of_newly_granted_project,
            sender=Project,
            dispatch_uid='nodeconductor.iaas.handlers.propagate_users_keys_to_clouds_of_newly_granted_project',
        )

        structure_role_revoked.connect(
            handlers.remove_stale_users_keys_from_clouds_of_revoked_project,
            sender=Project,
            dispatch_uid='nodeconductor.iaas.handlers.remove_stale_users_keys_from_clouds_of_revoked_project',
        )

        signals.post_save.connect(
            handlers.create_initial_security_groups,
            sender=CloudProjectMembership,
            dispatch_uid='nodeconductor.iaas.handlers.create_initial_security_groups',
        )

        # protect against a deletion of the Instance with connected backups
        # TODO: introduces dependency of IaaS on Backups, should be reconsidered
        signals.pre_delete.connect(
            handlers.prevent_deletion_of_instances_with_connected_backups,
            sender=Instance,
            dispatch_uid='nodeconductor.iaas.handlers.prevent_deletion_of_instances_with_connected_backups',
        )

        signals.pre_save.connect(
            core_handlers.preserve_fields_before_update,
            sender=Instance,
            dispatch_uid='nodeconductor.iaas.handlers.preserve_fields_before_update',
        )

        # if instance name is updated, zabbix host visible name should be also updated
        signals.post_save.connect(
            handlers.check_instance_name_update,
            sender=Instance,
            dispatch_uid='nodeconductor.iaas.handlers.check_instance_name_update',
        )

        signals.post_save.connect(
            quotas_handlers.add_quotas_to_scope,
            sender=CloudProjectMembership,
            dispatch_uid='nodeconductor.iaas.handlers.add_quotas_to_membership',
        )

        signals.pre_save.connect(
            handlers.set_cpm_default_availability_zone,
            sender=CloudProjectMembership,
            dispatch_uid='nodeconductor.iaas.handlers.set_cpm_default_availability_zone',
        )

        # increase nc_resource_count quota usage on instance creation
        signals.post_save.connect(
            handlers.change_customer_nc_instances_quota,
            sender=Instance,
            dispatch_uid='nodeconductor.iaas.handlers.increase_cutomer_nc_instances_quota',
        )

        # decrease nc_resource_count quota usage on instance deletion
        signals.post_delete.connect(
            handlers.change_customer_nc_instances_quota,
            sender=Instance,
            dispatch_uid='nodeconductor.iaas.handlers.decrease_cutomer_nc_instances_quota',
        )

        signals.post_save.connect(
            handlers.add_instance_uuid_to_user_data,
            sender=Instance,
            dispatch_uid='nodeconductor.iaas.handlers.add_instance_uuid_to_user_data',
        )
