from __future__ import unicode_literals

import logging

from django.contrib.contenttypes.fields import GenericRelation
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, URLValidator
from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from iptools.ipv4 import validate_cidr

from nodeconductor.core import models as core_models
from nodeconductor.cost_tracking import models as cost_tracking_models
from nodeconductor.iaas import managers
from nodeconductor.logging.loggers import LoggableMixin
from nodeconductor.structure import models as structure_models

logger = logging.getLogger(__name__)


@python_2_unicode_compatible
class OpenStackSettings(models.Model):
    """ OpenStack deployment admin credentials and settings """

    auth_url = models.URLField(max_length=200, unique=True, help_text='Keystone endpoint url')
    username = models.CharField(max_length=100)
    password = models.CharField(max_length=100)
    tenant_name = models.CharField(max_length=100)
    availability_zone = models.CharField(max_length=100, blank=True)

    def get_credentials(self):
        options = ('auth_url', 'username', 'password', 'tenant_name')
        return {opt: getattr(self, opt) for opt in options}

    def __str__(self):
        return self.auth_url

    class Meta:
        verbose_name = "OpenStack settings"
        verbose_name_plural = "OpenStack settings"


def validate_known_keystone_urls(value):
    if not OpenStackSettings.objects.filter(auth_url=value).exists():
        raise ValidationError('%s is not a known OpenStack deployment.' % value)


@python_2_unicode_compatible
class Cloud(core_models.UuidMixin, core_models.NameMixin, LoggableMixin,
            core_models.SynchronizableMixin, models.Model):
    """
    A cloud instance information.

    Represents parameters set that are necessary to connect to a particular cloud,
    such as connection endpoints, credentials, etc.
    """

    class Meta(object):
        unique_together = (
            ('customer', 'name'),
        )

    class Permissions(object):
        customer_path = 'customer'
        project_path = 'projects'
        project_group_path = 'customer__projects__project_groups'

    customer = models.ForeignKey(structure_models.Customer, related_name='clouds')
    projects = models.ManyToManyField(
        structure_models.Project, related_name='clouds', through='CloudProjectMembership')

    # OpenStack backend specific fields
    # Consider replacing it with credentials FK
    auth_url = models.CharField(max_length=200, help_text='Keystone endpoint url',
                                validators=[URLValidator(), validate_known_keystone_urls])

    def get_backend(self):
        # TODO: Support different clouds instead of hard-coding
        # Importing here to avoid circular imports hell
        from nodeconductor.iaas.backend import OpenStackBackend

        return OpenStackBackend()

    def get_statistics(self):
        return {s.key: s.value for s in self.stats.all()}

    @classmethod
    def get_url_name(cls):
        return 'cloud'

    def __str__(self):
        return self.name


Cloud._meta.get_field('state').default = core_models.SynchronizationStates.SYNCING_SCHEDULED


class ServiceStatistics(models.Model):
    cloud = models.ForeignKey(Cloud, related_name='stats')
    key = models.CharField(max_length=32)
    value = models.CharField(max_length=255)


@python_2_unicode_compatible
class CloudProjectMembership(core_models.SynchronizableMixin, structure_models.ServiceProjectLink):
    """
    This model represents many to many relationships between project and cloud
    """
    QUOTAS_NAMES = ['vcpu', 'ram', 'storage', 'max_instances', 'security_group_count', 'security_group_rule_count']

    cloud = models.ForeignKey(Cloud)

    # OpenStack backend specific fields
    username = models.CharField(max_length=100, blank=True)
    password = models.CharField(max_length=100, blank=True)

    tenant_id = models.CharField(max_length=64, blank=True)
    internal_network_id = models.CharField(max_length=64, blank=True)
    external_network_id = models.CharField(max_length=64, blank=True)

    availability_zone = models.CharField(
        max_length=100, blank=True,
        help_text='Optional availability group. Will be used for all instances provisioned in this tenant'
    )

    class Meta(object):
        unique_together = ('cloud', 'project')

    class Permissions(object):
        customer_path = 'cloud__customer'
        project_path = 'project'
        project_group_path = 'project__project_groups'

    def __str__(self):
        return '{0} | {1}'.format(self.cloud.name, self.project.name)

    def get_backend(self):
        return self.cloud.get_backend()

    def get_log_fields(self):
        return ('project', 'cloud', 'service')

    @property
    def service(self):
        # XXX: Temporary backward compatibility
        return self.cloud

    @classmethod
    def get_url_name(cls):
        """ This name will be used by generic relationships to membership model for URL creation """
        return 'cloudproject_membership'


CloudProjectMembership._meta.get_field('state').default = core_models.SynchronizationStates.SYNCING_SCHEDULED


@python_2_unicode_compatible
class Flavor(LoggableMixin, core_models.UuidMixin, core_models.NameMixin, models.Model):
    """
    A preset of computing resources.
    """

    class Permissions(object):
        customer_path = 'cloud__projects__customer'
        project_path = 'cloud__projects'
        project_group_path = 'cloud__projects__project_groups'

    class Meta(object):
        unique_together = (
            # OpenStack backend specific constraint
            ('cloud', 'backend_id'),
        )

    cloud = models.ForeignKey(Cloud, related_name='flavors')

    cores = models.PositiveSmallIntegerField(help_text='Number of cores in a VM')
    ram = models.PositiveIntegerField(help_text='Memory size in MiB')
    disk = models.PositiveIntegerField(help_text='Root disk size in MiB')

    # OpenStack backend specific fields
    backend_id = models.CharField(max_length=255)

    def __str__(self):
        return '%s (%s)' % (self.name, self.cloud)


@python_2_unicode_compatible
class Image(models.Model):
    class Meta(object):
        unique_together = (
            ('cloud', 'template'),
        )

    class Permissions(object):
        project_path = 'cloud__projects'
        project_group_path = 'cloud__projects__project_groups'

    cloud = models.ForeignKey(Cloud, related_name='images')
    template = models.ForeignKey('iaas.Template', related_name='images')

    min_disk = models.PositiveIntegerField(default=0, help_text='Minimum disk size in MiB')
    min_ram = models.PositiveIntegerField(default=0, help_text='Minimum memory size in MiB')

    backend_id = models.CharField(max_length=255)

    def __str__(self):
        return '{template} <-> {cloud}'.format(
            cloud=self.cloud.name,
            template=self.template.name,
        )


@python_2_unicode_compatible
class Template(core_models.UuidMixin,
               core_models.UiDescribableMixin,
               LoggableMixin,
               models.Model):
    """
    A template for the IaaS instance. If it is inactive, it is not visible to non-staff users.
    """
    class OsTypes(object):
        CENTOS6 = 'centos6'
        CENTOS7 = 'centos7'
        UBUNTU = 'ubuntu'
        RHEL6 = 'rhel6'
        RHEL7 = 'rhel7'
        FREEBSD = 'freebsd'
        WINDOWS = 'windows'
        OTHER = 'other'

        CHOICES = (
            (CENTOS6, 'Centos 6'),
            (CENTOS7, 'Centos 7'),
            (UBUNTU, 'Ubuntu'),
            (RHEL6, 'RedHat 6'),
            (RHEL7, 'RedHat 7'),
            (FREEBSD, 'FreeBSD'),
            (WINDOWS, 'Windows'),
            (OTHER, 'Other'),
        )

        CATEGORIES = {
            'linux': (CENTOS6, CENTOS7, UBUNTU, RHEL6, RHEL7)
        }

    # Model doesn't inherit NameMixin, because name field must be unique.
    name = models.CharField(max_length=150, unique=True)
    os = models.CharField(max_length=100, blank=True)
    os_type = models.CharField(max_length=10, choices=OsTypes.CHOICES, default=OsTypes.OTHER)
    is_active = models.BooleanField(default=False)
    sla_level = models.DecimalField(max_digits=6, decimal_places=4, null=True, blank=True)
    icon_name = models.CharField(max_length=100, blank=True)

    # fields for categorisation
    # XXX consider changing to tags
    type = models.CharField(max_length=100, blank=True, help_text='Template type')
    application_type = models.ForeignKey(cost_tracking_models.ApplicationType, null=True,
                                         help_text='Type of the application inside the template (optional)')

    def __str__(self):
        return self.name

    def get_log_fields(self):
        return ('uuid', 'name', 'applicaiton_type', 'type', 'os', 'os_type',)


@python_2_unicode_compatible
class TemplateMapping(core_models.DescribableMixin, models.Model):
    class Meta(object):
        unique_together = ('template', 'backend_image_id')

    template = models.ForeignKey(Template, related_name='mappings')
    backend_image_id = models.CharField(max_length=255)

    def __str__(self):
        return '{0} <-> {1}'.format(self.template.name, self.backend_image_id)


class FloatingIP(core_models.UuidMixin):
    class Permissions(object):
        customer_path = 'cloud_project_membership__cloud__customer'
        project_path = 'cloud_project_membership__project'
        project_group_path = 'cloud_project_membership__project__project_groups'

    cloud_project_membership = models.ForeignKey(
        CloudProjectMembership, related_name='floating_ips')

    address = models.GenericIPAddressField(protocol='IPv4')
    status = models.CharField(max_length=30)
    backend_id = models.CharField(max_length=255)
    backend_network_id = models.CharField(max_length=255, editable=False)


@python_2_unicode_compatible
class Instance(structure_models.Resource,
               structure_models.PaidResource,
               structure_models.BaseVirtualMachineMixin):
    """
    A generalization of a single virtual machine.

    Depending on a cloud the instance is deployed to
    it can be either a fully virtualized instance, or a container.
    """
    class Permissions(object):
        customer_path = 'cloud_project_membership__project__customer'
        project_path = 'cloud_project_membership__project'
        project_group_path = 'cloud_project_membership__project__project_groups'
        service_path = 'cloud_project_membership__cloud'

    class Services(object):
        IAAS = 'IaaS'
        PAAS = 'PaaS'

    SERVICE_TYPES = (
        (Services.IAAS, 'IaaS'), (Services.PAAS, 'PaaS'))

    DEFAULT_DATA_VOLUME_SIZE = 20 * 1024

    # This needs to be inlined in order to set on_delete
    cloud_project_membership = models.ForeignKey(
        CloudProjectMembership, related_name='instances', on_delete=models.PROTECT)
    # XXX: ideally these fields have to be added somewhere in iaas.backup module
    backups = GenericRelation('backup.Backup')
    backup_schedules = GenericRelation('backup.BackupSchedule')

    template = models.ForeignKey(Template, related_name='+')
    external_ips = models.GenericIPAddressField(null=True, blank=True, protocol='IPv4')
    internal_ips = models.GenericIPAddressField(null=True, blank=True, protocol='IPv4')

    # This field has to be changed to ChoiceField in NC-580
    installation_state = models.CharField(
        max_length=50, default='NO DATA', blank=True, help_text='State of post deploy installation process')

    # fields, defined by flavor
    flavor_name = models.CharField(max_length=255, blank=True)
    cores = models.PositiveSmallIntegerField(help_text='Number of cores in a VM')
    ram = models.PositiveIntegerField(help_text='Memory size in MiB')

    # OpenStack backend specific fields
    system_volume_id = models.CharField(max_length=255, blank=True)
    system_volume_size = models.PositiveIntegerField(help_text='Root disk size in MiB')
    data_volume_id = models.CharField(max_length=255, blank=True)
    data_volume_size = models.PositiveIntegerField(
        default=DEFAULT_DATA_VOLUME_SIZE, help_text='Data disk size in MiB', validators=[MinValueValidator(1 * 1024)])

    # Services specific fields
    agreed_sla = models.DecimalField(max_digits=6, decimal_places=4, null=True, blank=True)
    type = models.CharField(max_length=10, choices=SERVICE_TYPES, default=Services.IAAS)

    objects = managers.InstanceManager()

    def __str__(self):
        return self.name

    @property
    def service_project_link(self):
        # For consistency with other resources
        return self.cloud_project_membership

    def get_backend(self):
        return self.cloud_project_membership.get_backend()

    def get_instance_security_groups(self):
        return InstanceSecurityGroup.objects.filter(instance=self)

    def _init_instance_licenses(self):
        """
        Create new instance licenses from template licenses
        """
        for template_license in self.template.template_licenses.all():
            InstanceLicense.objects.create(
                instance=self,
                template_license=template_license,
            )

    def save(self, *args, **kwargs):
        created = self.pk is None
        super(Instance, self).save(*args, **kwargs)
        if created:
            self._init_instance_licenses()

    def get_log_fields(self):
        return (
            'uuid', 'name', 'type', 'cloud_project_membership', 'ram',
            'cores', 'data_volume_size', 'system_volume_size', 'installation_state', 'template',
        )

    @classmethod
    def get_url_name(cls):
        return 'instance'


@python_2_unicode_compatible
class InstanceSlaHistory(models.Model):
    period = models.CharField(max_length=10)
    instance = models.ForeignKey(Instance, related_name='slas')
    value = models.DecimalField(max_digits=11, decimal_places=4, null=True, blank=True)

    class Meta:
        verbose_name = 'Instance SLA history'
        verbose_name_plural = 'Instance SLA histories'
        unique_together = ('period', 'instance')

    def __str__(self):
        return 'SLA for %s during %s: %s' % (self.instance, self.period, self.value)


@python_2_unicode_compatible
class InstanceSlaHistoryEvents(models.Model):
    EVENTS = (
        ('U', 'DOWN'),
        ('D', 'UP'),
    )

    instance = models.ForeignKey(InstanceSlaHistory, related_name='events')
    timestamp = models.IntegerField()
    state = models.CharField(max_length=1, choices=EVENTS)

    def __str__(self):
        return '%s - %s' % (self.timestamp, self.state)


@python_2_unicode_compatible
class TemplateLicense(core_models.UuidMixin,
                      core_models.NameMixin,
                      models.Model):
    class Services(object):
        IAAS = 'IaaS'
        PAAS = 'PaaS'
        SAAS = 'SaaS'
        BPAAS = 'BPaaS'

    SERVICE_TYPES = (
        (Services.IAAS, 'IaaS'), (Services.PAAS, 'PaaS'), (Services.SAAS, 'SaaS'), (Services.BPAAS, 'BPaaS'))

    license_type = models.CharField(max_length=127)
    templates = models.ManyToManyField(Template, related_name='template_licenses')
    service_type = models.CharField(max_length=10, choices=SERVICE_TYPES)

    def __str__(self):
        return '%s - %s' % (self.license_type, self.name)

    def get_projects(self):
        return structure_models.Project.objects.filter(
            clouds__images__template__template_licenses=self).distinct()

    def get_projects_groups(self):
        return structure_models.ProjectGroup.objects.filter(
            projects__clouds__images__template__template_licenses=self).distinct()


@python_2_unicode_compatible
class InstanceLicense(core_models.UuidMixin, models.Model):
    template_license = models.ForeignKey(TemplateLicense, related_name='instance_licenses')
    instance = models.ForeignKey(Instance, related_name='instance_licenses')

    class Permissions(object):
        customer_path = 'instance__cloud_project_membership__project__customer'
        project_path = 'instance__cloud_project_membership__project'
        project_group_path = 'instance__cloud_project_membership__project__project_groups'

    def __str__(self):
        return 'License: %s for %s' % (self.template_license, self.instance)


@python_2_unicode_compatible
class SecurityGroup(core_models.UuidMixin,
                    core_models.DescribableMixin,
                    core_models.NameMixin,
                    core_models.SynchronizableMixin,
                    models.Model):

    class Permissions(object):
        customer_path = 'cloud_project_membership__project__customer'
        project_path = 'cloud_project_membership__project'
        project_group_path = 'cloud_project_membership__project__project_groups'

    """
    This class contains OpenStack security groups.
    """

    cloud_project_membership = models.ForeignKey(
        CloudProjectMembership, related_name='security_groups')

    # OpenStack backend specific fields
    backend_id = models.CharField(max_length=128, blank=True,
                                  help_text='Reference to a SecurityGroup in a remote cloud')

    def __str__(self):
        return self.name


SecurityGroup._meta.get_field('state').default = core_models.SynchronizationStates.SYNCING_SCHEDULED


class SecurityGroupRuleValidationMixin(object):
    """
    Mixin for security group rule validation.
    """
    def validate_icmp(self):
        if self.from_port is not None and not -1 <= self.from_port <= 255:
            raise ValidationError('Wrong value for "from_port": '
                                  'expected value in range [-1, 255], found %d' % self.from_port)
        if self.to_port is not None and not -1 <= self.to_port <= 255:
            raise ValidationError('Wrong value for "to_port": '
                                  'expected value in range [-1, 255], found %d' % self.to_port)

    def validate_port(self):
        if self.from_port is not None and self.to_port is not None:
            if self.from_port > self.to_port:
                raise ValidationError('"from_port" should be less or equal to "to_port"')
        if self.from_port is not None and self.from_port < 1:
            raise ValidationError('Wrong value for "from_port": '
                                  'expected value in range [1, 65535], found %d' % self.from_port)
        if self.to_port is not None and self.to_port < 1:
            raise ValidationError('Wrong value for "to_port": '
                                  'expected value in range [1, 65535], found %d' % self.to_port)

    def validate_cidr(self):
        if not self.cidr:
            return

        if not validate_cidr(self.cidr):
            raise ValidationError('Wrong cidr value. Expected cidr format: <0-255>.<0-255>.<0-255>.<0-255>/<0-32>')

    def clean(self):
        if self.protocol == 'icmp':
            self.validate_icmp()
        elif self.protocol in ('tcp', 'udp'):
            self.validate_port()
        else:
            raise ValidationError('Wrong value for "protocol": '
                                  'expected one of (tcp, udp, icmp), found %s' % self.protocol)
        self.validate_cidr()


@python_2_unicode_compatible
class SecurityGroupRule(SecurityGroupRuleValidationMixin, models.Model):

    tcp = 'tcp'
    udp = 'udp'
    icmp = 'icmp'

    PROTOCOL_CHOICES = (
        (tcp, 'tcp'),
        (udp, 'udp'),
        (icmp, 'icmp'),
    )

    group = models.ForeignKey(SecurityGroup, related_name='rules')

    protocol = models.CharField(max_length=4, blank=True, choices=PROTOCOL_CHOICES)
    from_port = models.IntegerField(validators=[MaxValueValidator(65535)], null=True)
    to_port = models.IntegerField(validators=[MaxValueValidator(65535)], null=True)
    cidr = models.CharField(max_length=32, blank=True)

    # OpenStack backend specific fields
    backend_id = models.CharField(max_length=128, blank=True)

    def __str__(self):
        return '%s (%s): %s (%s -> %s)' % \
               (self.group, self.protocol, self.cidr, self.from_port, self.to_port)


class InstanceSecurityGroup(models.Model):
    """
    Cloud security group added to instance
    """
    class Permissions(object):
        project_path = 'instance__project'
        project_group_path = 'instance__project__project_groups'

    instance = models.ForeignKey(Instance, related_name='security_groups')
    security_group = models.ForeignKey(SecurityGroup, related_name='instance_groups')


class IpMapping(core_models.UuidMixin, models.Model):
    class Permissions(object):
        project_path = 'project'
        customer_path = 'project__customer'
        project_group_path = 'project__project_groups'

    public_ip = models.GenericIPAddressField(null=False)
    private_ip = models.GenericIPAddressField(null=False)
    project = models.ForeignKey(structure_models.Project, related_name='ip_mappings')
