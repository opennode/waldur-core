from __future__ import unicode_literals

from django.apps import AppConfig
from django.db.models import signals

from nodeconductor.core import handlers as core_handlers
from nodeconductor.core.signals import pre_serializer_fields
from nodeconductor.cost_tracking import CostTrackingRegister
from nodeconductor.structure.models import Project
from nodeconductor.quotas import handlers as quotas_handlers


class IaasConfig(AppConfig):
    name = 'nodeconductor.iaas'
    verbose_name = "NodeConductor IaaS"

    # See, https://docs.djangoproject.com/en/1.7/ref/applications/#django.apps.AppConfig.ready
    def ready(self):
        Instance = self.get_model('Instance')
        Cloud = self.get_model('Cloud')
        CloudProjectMembership = self.get_model('CloudProjectMembership')

        from nodeconductor.iaas import handlers, cost_tracking
        from nodeconductor.structure.serializers import CustomerSerializer, ProjectSerializer

        CostTrackingRegister.register(self.label, cost_tracking.IaaSCostTrackingBackend)

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
            quotas_handlers.add_quotas_to_scope,
            sender=CloudProjectMembership,
            dispatch_uid='nodeconductor.iaas.handlers.add_quotas_to_cloud_project_membership',
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

        signals.pre_save.connect(
            handlers.set_cpm_default_availability_zone,
            sender=CloudProjectMembership,
            dispatch_uid='nodeconductor.iaas.handlers.set_cpm_default_availability_zone',
        )

        signals.post_save.connect(
            handlers.increase_quotas_usage_on_instance_creation,
            sender=Instance,
            dispatch_uid='nodeconductor.iaas.handlers.increase_quotas_usage_on_instance_creation',
        )

        signals.post_delete.connect(
            handlers.decrease_quotas_usage_on_instances_deletion,
            sender=Instance,
            dispatch_uid='nodeconductor.iaas.handlers.decrease_quotas_usage_on_instances_deletion',
        )

        signals.post_save.connect(
            handlers.change_customer_nc_service_quota,
            sender=Cloud,
            dispatch_uid='nodeconductor.iaas.handlers.increase_customer_nc_service_quota'
        )

        signals.post_delete.connect(
            handlers.change_customer_nc_service_quota,
            sender=Cloud,
            dispatch_uid='nodeconductor.iaas.handlers.decrease_customer_nc_service_quota'
        )

        signals.post_save.connect(
            handlers.check_project_name_update,
            sender=Project,
            dispatch_uid='nodeconductor.iaas.handlers.check_project_name_update'
        )
