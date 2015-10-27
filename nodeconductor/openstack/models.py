from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator
from django.utils.encoding import python_2_unicode_compatible
from model_utils import FieldTracker

from nodeconductor.core import models as core_models
from nodeconductor.structure import models as structure_models
from nodeconductor.quotas.models import QuotaModelMixin
from nodeconductor.iaas.models import PaidInstance, SecurityGroupRuleValidationMixin
from nodeconductor.logging.log import LoggableMixin


class OpenStackService(structure_models.Service):
    projects = models.ManyToManyField(
        structure_models.Project, related_name='openstack_services', through='OpenStackServiceProjectLink')

    class Meta:
        verbose_name = 'OpenStack service'
        verbose_name_plural = 'OpenStack services'

    @property
    def auth_url(self):
        # XXX: Temporary backward compatibility
        return self.settings.backend_url


class OpenStackServiceProjectLink(QuotaModelMixin, structure_models.ServiceProjectLink):
    QUOTAS_NAMES = ['vcpu', 'ram', 'storage', 'instances', 'security_group_count', 'security_group_rule_count',
                    'floating_ip_count']

    service = models.ForeignKey(OpenStackService)

    tenant_id = models.CharField(max_length=64, blank=True)
    internal_network_id = models.CharField(max_length=64, blank=True)
    external_network_id = models.CharField(max_length=64, blank=True)

    availability_zone = models.CharField(
        max_length=100, blank=True,
        help_text='Optional availability group. Will be used for all instances provisioned in this tenant'
    )

    class Meta:
        unique_together = ('service', 'project')
        verbose_name = 'OpenStack service project link'
        verbose_name_plural = 'OpenStack service project links'

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

    def get_backend(self):
        return super(OpenStackServiceProjectLink, self).get_backend(tenant_id=self.tenant_id)


class Flavor(LoggableMixin, structure_models.ServiceProperty):
    cores = models.PositiveSmallIntegerField(help_text='Number of cores in a VM')
    ram = models.PositiveIntegerField(help_text='Memory size in MiB')
    disk = models.PositiveIntegerField(help_text='Root disk size in MiB')


class Image(structure_models.ServiceProperty):
    min_disk = models.PositiveIntegerField(default=0, help_text='Minimum disk size in MiB')
    min_ram = models.PositiveIntegerField(default=0, help_text='Minimum memory size in MiB')


@python_2_unicode_compatible
class SecurityGroup(core_models.UuidMixin,
                    core_models.NameMixin,
                    core_models.DescribableMixin,
                    core_models.SynchronizableMixin):

    class Permissions(object):
        customer_path = 'service_project_link__project__customer'
        project_path = 'service_project_link__project'
        project_group_path = 'service_project_link__project__project_groups'

    service_project_link = models.ForeignKey(
        OpenStackServiceProjectLink, related_name='security_groups')

    backend_id = models.CharField(max_length=128, blank=True)

    def __str__(self):
        return self.name

    @classmethod
    def get_url_name(cls):
        return 'openstack-sgp'


SecurityGroup._meta.get_field('state').default = core_models.SynchronizationStates.SYNCING_SCHEDULED


@python_2_unicode_compatible
class SecurityGroupRule(SecurityGroupRuleValidationMixin, models.Model):
    TCP = 'tcp'
    UDP = 'udp'
    ICMP = 'icmp'

    CHOICES = (
        (TCP, 'tcp'),
        (UDP, 'udp'),
        (ICMP, 'icmp'),
    )

    security_group = models.ForeignKey(SecurityGroup, related_name='rules')
    protocol = models.CharField(max_length=4, blank=True, choices=CHOICES)
    from_port = models.IntegerField(validators=[MaxValueValidator(65535)], null=True)
    to_port = models.IntegerField(validators=[MaxValueValidator(65535)], null=True)
    cidr = models.CharField(max_length=32, blank=True)

    backend_id = models.CharField(max_length=128, blank=True)

    def __str__(self):
        return '%s (%s): %s (%s -> %s)' % \
               (self.security_group, self.protocol, self.cidr, self.from_port, self.to_port)


class FloatingIP(core_models.UuidMixin):

    class Permissions(object):
        customer_path = 'service_project_link__project__customer'
        project_path = 'service_project_link__project'
        project_group_path = 'service_project_link__project__project_groups'

    service_project_link = models.ForeignKey(
        OpenStackServiceProjectLink, related_name='floating_ips')

    address = models.GenericIPAddressField(protocol='IPv4')
    status = models.CharField(max_length=30)
    backend_id = models.CharField(max_length=255)
    backend_network_id = models.CharField(max_length=255, editable=False)

    tracker = FieldTracker()


class Instance(structure_models.VirtualMachineMixin, structure_models.Resource, PaidInstance):
    DEFAULT_DATA_VOLUME_SIZE = 20 * 1024

    service_project_link = models.ForeignKey(
        OpenStackServiceProjectLink, related_name='instances', on_delete=models.PROTECT)

    external_ips = models.GenericIPAddressField(null=True, blank=True, protocol='IPv4')
    internal_ips = models.GenericIPAddressField(null=True, blank=True, protocol='IPv4')

    # OpenStack backend specific fields
    system_volume_id = models.CharField(max_length=255, blank=True)
    system_volume_size = models.PositiveIntegerField(default=0, help_text='Root disk size in MiB')
    data_volume_id = models.CharField(max_length=255, blank=True)
    data_volume_size = models.PositiveIntegerField(
        default=DEFAULT_DATA_VOLUME_SIZE, help_text='Data disk size in MiB', validators=[MinValueValidator(1 * 1024)])

    tracker = FieldTracker()

    @property
    def cloud_project_membership(self):
        # Temporary backward compatibility
        return self.service_project_link

    def get_log_fields(self):
        return (
            'uuid', 'name', 'type', 'service_project_link', 'ram', 'cores',
            'data_volume_size', 'system_volume_size',
        )


class InstanceSecurityGroup(models.Model):
    class Permissions(object):
        project_path = 'instance__project'
        project_group_path = 'instance__project__project_groups'

    instance = models.ForeignKey(Instance, related_name='security_groups')
    security_group = models.ForeignKey(SecurityGroup, related_name='instance_groups')
