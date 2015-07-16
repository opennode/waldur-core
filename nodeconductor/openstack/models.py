from django.db import models
from django.core.validators import MinValueValidator

from nodeconductor.structure import models as structure_models
from nodeconductor.logging.log import LoggableMixin


class Service(LoggableMixin, structure_models.Service):
    projects = models.ManyToManyField(
        structure_models.Project, related_name='+', through='ServiceProjectLink')

    @property
    def auth_url(self):
        # XXX: Temporary backward compatibility
        return self.settings.backend_url


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

    @property
    def cloud(self):
        # XXX: Temporary backward compatibility
        return self.service

    @property
    def username(self):
        # XXX: Temporary backward compatibility
        return self.service.settings.username

    @property
    def password(self):
        # XXX: Temporary backward compatibility
        return self.service.settings.password

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


class Instance(LoggableMixin, structure_models.VirtualMachineMixin, structure_models.Resource):
    DEFAULT_DATA_VOLUME_SIZE = 20 * 1024

    service_project_link = models.ForeignKey(
        ServiceProjectLink, related_name='instances', on_delete=models.PROTECT)

    external_ips = models.GenericIPAddressField(null=True, blank=True, protocol='IPv4')
    internal_ips = models.GenericIPAddressField(null=True, blank=True, protocol='IPv4')

    # fields, defined by flavor
    cores = models.PositiveSmallIntegerField(default=0, help_text='Number of cores in a VM')
    ram = models.PositiveIntegerField(default=0, help_text='Memory size in MiB')

    # OpenStack backend specific fields
    system_volume_id = models.CharField(max_length=255, blank=True)
    system_volume_size = models.PositiveIntegerField(default=0, help_text='Root disk size in MiB')
    data_volume_id = models.CharField(max_length=255, blank=True)
    data_volume_size = models.PositiveIntegerField(
        default=DEFAULT_DATA_VOLUME_SIZE, help_text='Data disk size in MiB', validators=[MinValueValidator(1 * 1024)])

    @property
    def cloud_project_membership(self):
        # Temporary backward compatibility
        return self.service_project_link

    def get_log_fields(self):
        return (
            'uuid', 'name', 'type', 'service_project_link', 'ram', 'cores',
            'data_volume_size', 'system_volume_size',
        )
