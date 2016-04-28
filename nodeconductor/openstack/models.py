from __future__ import unicode_literals

from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator
from django.template.defaultfilters import slugify
from django.utils.encoding import python_2_unicode_compatible
from django_fsm import transition, FSMIntegerField
from jsonfield import JSONField
from model_utils import FieldTracker
from urlparse import urlparse

from nodeconductor.core import models as core_models
from nodeconductor.iaas.models import SecurityGroupRuleValidationMixin
from nodeconductor.logging.loggers import LoggableMixin
from nodeconductor.openstack.backup import BackupBackend, BackupScheduleBackend
from nodeconductor.openstack.managers import BackupManager
from nodeconductor.quotas.fields import QuotaField
from nodeconductor.quotas.models import QuotaModelMixin
from nodeconductor.structure import models as structure_models
from nodeconductor.structure.utils import get_coordinates_by_ip, Coordinates


class OpenStackService(structure_models.Service):
    projects = models.ManyToManyField(
        structure_models.Project, related_name='openstack_services', through='OpenStackServiceProjectLink')

    class Meta:
        unique_together = ('customer', 'settings')
        verbose_name = 'OpenStack service'
        verbose_name_plural = 'OpenStack services'

    @property
    def auth_url(self):
        # XXX: Temporary backward compatibility
        return self.settings.backend_url


class OpenStackServiceProjectLink(structure_models.ServiceProjectLink):

    class Quotas(QuotaModelMixin.Quotas):
        vcpu = QuotaField(default_limit=20, is_backend=True)
        ram = QuotaField(default_limit=51200, is_backend=True)
        storage = QuotaField(default_limit=1024000, is_backend=True)
        instances = QuotaField(default_limit=30, is_backend=True)
        security_group_count = QuotaField(default_limit=100, is_backend=True)
        security_group_rule_count = QuotaField(default_limit=100, is_backend=True)
        floating_ip_count = QuotaField(default_limit=50, is_backend=True)

    service = models.ForeignKey(OpenStackService)

    class Meta(structure_models.ServiceProjectLink.Meta):
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

    def get_backend(self):
        return super(OpenStackServiceProjectLink, self).get_backend(tenant_id=self.tenant_id)

    # XXX: temporary method, should be removed after instance will have tenant as field
    @property
    def tenant(self):
        if not hasattr(self, '_tenant'):
            self._tenant = self.tenants.first()
        return self._tenant

    # XXX: temporary method, should be removed after instance will have tenant as field
    @property
    def internal_network_id(self):
        return self.tenant.internal_network_id if self.tenant else None

    # XXX: temporary method, should be removed after instance will have tenant as field
    @property
    def external_network_id(self):
        return self.tenant.external_network_id if self.tenant else None

    # XXX: temporary method, should be removed after instance will have tenant as field
    @property
    def availability_zone(self):
        return self.tenant.availability_zone if self.tenant else None

    # XXX: temporary method, should be removed after instance will have tenant as field
    @property
    def tenant_id(self):
        return self.tenant.backend_id if self.tenant else None

    # XXX: temporary method, should be removed after instance will have tenant as field
    def get_tenant_name(self):
        proj = self.project
        return '%(project_name)s-%(project_uuid)s' % {
            'project_name': ''.join([c for c in proj.name if ord(c) < 128])[:15],
            'project_uuid': proj.uuid.hex[:4]
        }

    # XXX: temporary method, should be removed after instance will have tenant as field
    def create_tenant(self):
        name = self.get_tenant_name()
        return Tenant.objects.create(name=name, service_project_link=self, user_username=slugify(name)[:30] + '-user')


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
                    core_models.StateMixin):

    class Permissions(object):
        customer_path = 'service_project_link__project__customer'
        project_path = 'service_project_link__project'
        project_group_path = 'service_project_link__project__project_groups'

    service_project_link = models.ForeignKey(
        OpenStackServiceProjectLink, related_name='security_groups')

    backend_id = models.CharField(max_length=128, blank=True)

    def __str__(self):
        return '%s (%s)' % (self.name, self.service_project_link)

    def get_backend(self):
        return self.service_project_link.get_backend()

    @classmethod
    def get_url_name(cls):
        return 'openstack-sgp'


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


class Instance(structure_models.VirtualMachineMixin,
               structure_models.PaidResource,
               structure_models.Resource):

    DEFAULT_DATA_VOLUME_SIZE = 20 * 1024

    service_project_link = models.ForeignKey(
        OpenStackServiceProjectLink, related_name='instances', on_delete=models.PROTECT)

    # OpenStack backend specific fields
    system_volume_id = models.CharField(max_length=255, blank=True)
    system_volume_size = models.PositiveIntegerField(default=0, help_text='Root disk size in MiB')
    data_volume_id = models.CharField(max_length=255, blank=True)
    data_volume_size = models.PositiveIntegerField(
        default=DEFAULT_DATA_VOLUME_SIZE, help_text='Data disk size in MiB', validators=[MinValueValidator(1 * 1024)])

    flavor_name = models.CharField(max_length=255, blank=True)
    flavor_disk = models.PositiveIntegerField(default=0, help_text='Flavor disk size in MiB')

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

    def detect_coordinates(self):
        settings = self.service_project_link.service.settings
        data = settings.options.get('coordinates')
        if data:
            return Coordinates(latitude=data['latitude'],
                               longitude=data['longitude'])
        else:
            hostname = urlparse(settings.backend_url).hostname
            if hostname:
                return get_coordinates_by_ip(hostname)


class InstanceSecurityGroup(models.Model):

    class Permissions(object):
        project_path = 'instance__project'
        project_group_path = 'instance__project__project_groups'

    instance = models.ForeignKey(Instance, related_name='security_groups')
    security_group = models.ForeignKey(SecurityGroup, related_name='instance_groups')


class BackupSchedule(core_models.UuidMixin,
                     core_models.DescribableMixin,
                     core_models.ScheduleMixin,
                     LoggableMixin):

    class Permissions(object):
        customer_path = 'instance__service_project_link__project__customer'
        project_path = 'instance__service_project_link__project'
        project_group_path = 'instance__service_project_link__project__project_groups'

    instance = models.ForeignKey(Instance, related_name='backup_schedules')
    retention_time = models.PositiveIntegerField(
        help_text='Retention time in days')  # if 0 - backup will be kept forever
    maximal_number_of_backups = models.PositiveSmallIntegerField()

    @classmethod
    def get_url_name(cls):
        return 'openstack-schedule'

    def get_backend(self):
        return BackupScheduleBackend(self)


class Backup(core_models.UuidMixin,
             core_models.DescribableMixin,
             LoggableMixin):

    class Permissions(object):
        customer_path = 'instance__service_project_link__project__customer'
        project_path = 'instance__service_project_link__project'
        project_group_path = 'instance__service_project_link__project__project_groups'

    class States(object):
        READY = 1
        BACKING_UP = 2
        RESTORING = 3
        DELETING = 4
        ERRED = 5
        DELETED = 6

        CHOICES = (
            (READY, 'Ready'),
            (BACKING_UP, 'Backing up'),
            (RESTORING, 'Restoring'),
            (DELETING, 'Deleting'),
            (ERRED, 'Erred'),
            (DELETED, 'Deleted'),
        )

    instance = models.ForeignKey(Instance, related_name='backups')
    backup_schedule = models.ForeignKey(BackupSchedule, blank=True, null=True,
                                        on_delete=models.SET_NULL,
                                        related_name='backups')
    kept_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Guaranteed time of backup retention. If null - keep forever.')

    created_at = models.DateTimeField(auto_now_add=True)

    state = FSMIntegerField(default=States.READY, choices=States.CHOICES)
    metadata = JSONField(
        blank=True,
        help_text='Additional information about backup, can be used for backup restoration or deletion',
    )

    objects = BackupManager()

    def get_backend(self):
        return BackupBackend(self)

    @classmethod
    def get_url_name(cls):
        return 'openstack-backup'

    @transition(field=state, source=States.READY, target=States.BACKING_UP)
    def starting_backup(self):
        pass

    @transition(field=state, source=States.BACKING_UP, target=States.READY)
    def confirm_backup(self):
        pass

    @transition(field=state, source=States.READY, target=States.RESTORING)
    def starting_restoration(self):
        pass

    @transition(field=state, source=States.RESTORING, target=States.READY)
    def confirm_restoration(self):
        pass

    @transition(field=state, source=States.READY, target=States.DELETING)
    def starting_deletion(self):
        pass

    @transition(field=state, source=States.DELETING, target=States.DELETED)
    def confirm_deletion(self):
        pass

    @transition(field=state, source='*', target=States.ERRED)
    def set_erred(self):
        pass


class Tenant(core_models.RuntimeStateMixin, core_models.StateMixin,
             structure_models.PrivateCloudMixin, structure_models.ResourceMixin):
    service_project_link = models.ForeignKey(
        OpenStackServiceProjectLink, related_name='tenants', on_delete=models.PROTECT)

    internal_network_id = models.CharField(max_length=64, blank=True)
    external_network_id = models.CharField(max_length=64, blank=True)
    availability_zone = models.CharField(
        max_length=100, blank=True,
        help_text='Optional availability group. Will be used for all instances provisioned in this tenant'
    )
    user_username = models.CharField(max_length=50, blank=True)
    user_password = models.CharField(max_length=50, blank=True)

    tracker = FieldTracker()

    def get_backend(self):
        return self.service_project_link.service.get_backend(tenant_id=self.backend_id)
