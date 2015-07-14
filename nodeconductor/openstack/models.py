from django.db import models

from nodeconductor.structure import models as structure_models
from nodeconductor.logging.log import LoggableMixin


class Service(LoggableMixin, structure_models.Service):
    projects = models.ManyToManyField(
        structure_models.Project, related_name='+', through='ServiceProjectLink')


class ServiceProjectLink(LoggableMixin, structure_models.ServiceProjectLink):
    QUOTAS_NAMES = ['vcpu', 'ram', 'storage', 'max_instances',
                    'security_group_count', 'security_group_rule_count']

    service = models.ForeignKey(Service)

    tenant_id = models.CharField(max_length=64, blank=True)
    internal_network_id = models.CharField(max_length=64, blank=True)

    availability_zone = models.CharField(
        max_length=100, blank=True,
        help_text='Optional availability group. Will be used for all instances provisioned in this tenant'
    )

    def get_quota_parents(self):
        return [self.project]

    def get_log_fields(self):
        return ('project', 'cloud',)

    def get_backend(self):
        return super(ServiceProjectLink, self).get_backend(tenant_id=self.tenant_id)


class Flavor(LoggableMixin, structure_models.ServiceProperty):
    cores = models.PositiveSmallIntegerField(help_text='Number of cores in a VM')
    ram = models.PositiveIntegerField(help_text='Memory size in MiB')
    disk = models.PositiveIntegerField(help_text='Root disk size in MiB')


class Image(structure_models.ServiceProperty):
    min_disk = models.PositiveIntegerField(default=0, help_text='Minimum disk size in MiB')
    min_ram = models.PositiveIntegerField(default=0, help_text='Minimum memory size in MiB')
