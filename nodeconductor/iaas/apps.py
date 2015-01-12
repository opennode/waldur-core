from __future__ import unicode_literals

from django.apps import AppConfig
from django.db.models import signals

from nodeconductor.core.models import SshPublicKey
from nodeconductor.core.signals import pre_serializer_fields
from nodeconductor.iaas import handlers
from nodeconductor.structure.models import Project
from nodeconductor.structure.signals import structure_role_granted


class IaasConfig(AppConfig):
    name = 'nodeconductor.iaas'
    verbose_name = "NodeConductor IaaS"

    # See, https://docs.djangoproject.com/en/1.7/ref/applications/#django.apps.AppConfig.ready
    def ready(self):
        Instance = self.get_model('Instance')
        CloudProjectMembership = self.get_model('CloudProjectMembership')

        from nodeconductor.structure.serializers import CustomerSerializer, ProjectSerializer

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

        structure_role_granted.connect(
            handlers.propagate_users_keys_to_clouds_of_newly_granted_project,
            sender=Project,
            dispatch_uid='nodeconductor.iaas.handlers.propagate_users_keys_to_clouds_of_newly_granted_project',
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

