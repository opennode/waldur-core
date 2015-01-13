from __future__ import unicode_literals

import logging
from decimal import Decimal

from django.contrib.contenttypes import generic as ct_generic
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, URLValidator
from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from django_fsm import FSMIntegerField
from django_fsm import transition

from nodeconductor.core import models as core_models
from nodeconductor.iaas.backend import CloudBackendError
from nodeconductor.structure import models as structure_models


logger = logging.getLogger(__name__)


def validate_known_keystone_urls(value):
    from nodeconductor.iaas.backend.openstack import OpenStackBackend

    backend = OpenStackBackend()
    try:
        backend.get_credentials(value)
    except CloudBackendError:
        raise ValidationError('%s is not a known OpenStack deployment.' % value)


@python_2_unicode_compatible
class Cloud(core_models.UuidMixin, core_models.SynchronizableMixin, models.Model):
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

    name = models.CharField(max_length=100)
    customer = models.ForeignKey(structure_models.Customer, related_name='clouds')
    projects = models.ManyToManyField(
        structure_models.Project, related_name='clouds', through='CloudProjectMembership')

    # OpenStack backend specific fields
    auth_url = models.CharField(max_length=200, help_text='Keystone endpoint url',
                                validators=[URLValidator(), validate_known_keystone_urls])

    def get_backend(self):
        # TODO: Support different clouds instead of hard-coding
        # Importing here to avoid circular imports hell
        from nodeconductor.iaas.backend.openstack import OpenStackBackend

        return OpenStackBackend()

    def __str__(self):
        return self.name


@python_2_unicode_compatible
class CloudProjectMembership(core_models.SynchronizableMixin, models.Model):
    """
    This model represents many to many relationships between project and cloud
    """

    cloud = models.ForeignKey(Cloud)
    project = models.ForeignKey(structure_models.Project)

    # OpenStack backend specific fields
    username = models.CharField(max_length=100, blank=True)
    password = models.CharField(max_length=100, blank=True)

    tenant_id = models.CharField(max_length=64, blank=True)

    class Meta(object):
        unique_together = ('cloud', 'tenant_id')

    class Permissions(object):
        customer_path = 'cloud__customer'
        project_path = 'project'
        project_group_path = 'project__project_groups'

    def __str__(self):
        return '{0} | {1}'.format(self.cloud.name, self.project.name)


class CloudProjectMember(models.Model):
    class Meta(object):
        abstract = True

    cloud_project_membership = models.ForeignKey(CloudProjectMembership, related_name='+')


@python_2_unicode_compatible
class Flavor(core_models.UuidMixin, models.Model):
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

    name = models.CharField(max_length=100)
    cloud = models.ForeignKey(Cloud, related_name='flavors')

    cores = models.PositiveSmallIntegerField(help_text='Number of cores in a VM')
    ram = models.PositiveIntegerField(help_text='Memory size in MiB')
    disk = models.PositiveIntegerField(help_text='Root disk size in MiB')

    # OpenStack backend specific fields
    backend_id = models.CharField(max_length=255)

    def __str__(self):
        return self.name


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
               models.Model):
    """
    A template for the IaaS instance. If it is inactive, it is not visible to non-staff users.
    """
    name = models.CharField(max_length=100, unique=True)
    os = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=False)
    sla_level = models.DecimalField(max_digits=6, decimal_places=4, null=True, blank=True)
    setup_fee = models.DecimalField(max_digits=9, decimal_places=3, null=True, blank=True,
                                    validators=[MinValueValidator(Decimal('0.1')),
                                                MaxValueValidator(Decimal('100000.0'))])
    monthly_fee = models.DecimalField(max_digits=9, decimal_places=3, null=True, blank=True,
                                      validators=[MinValueValidator(Decimal('0.1')),
                                                  MaxValueValidator(Decimal('100000.0'))])

    def __str__(self):
        return self.name


@python_2_unicode_compatible
class TemplateMapping(core_models.DescribableMixin, models.Model):
    class Meta(object):
        unique_together = ('template', 'backend_image_id')

    template = models.ForeignKey(Template, related_name='mappings')
    backend_image_id = models.CharField(max_length=255)

    def __str__(self):
        return '{0} <-> {1}'.format(self.template.name, self.backend_image_id)


class AbstractResourceQuota(models.Model):
    """ Abstract model for membership quotas """

    class Meta(object):
        abstract = True

    vcpu = models.PositiveIntegerField(help_text='Virtual CPUs')
    ram = models.FloatField(help_text='RAM size')
    storage = models.FloatField(help_text='Storage size (incl. backup)')
    max_instances = models.PositiveIntegerField(help_text='Number of running instances')
    backup_storage = models.FloatField(default=200*1024, help_text='Backup storage size')


# TODO: Refactor to use CloudProjectMember
class ResourceQuota(AbstractResourceQuota):
    """ CloudProjectMembership quota """
    cloud_project_membership = models.OneToOneField('CloudProjectMembership', related_name='resource_quota')


# TODO: Refactor to use CloudProjectMember
class ResourceQuotaUsage(AbstractResourceQuota):
    """ CloudProjectMembership quota usage """
    cloud_project_membership = models.OneToOneField('CloudProjectMembership', related_name='resource_quota_usage')


class FloatingIP(core_models.UuidMixin, CloudProjectMember):
    class Permissions(object):
        customer_path = 'cloud_project_membership__cloud__customer'
        project_path = 'cloud_project_membership__project'
        project_group_path = 'cloud_project_membership__project__project_groups'

    address = models.GenericIPAddressField(protocol='IPv4')
    status = models.CharField(max_length=30)
    backend_id = models.CharField(max_length=255)


@python_2_unicode_compatible
class Instance(core_models.UuidMixin,
               core_models.DescribableMixin,
               # This needs to be inlined in order to set on_delete
               # CloudProjectMember,
               models.Model):
    """
    A generalization of a single virtual machine.

    Depending on a cloud the instance is deployed to
    it can be either a fully virtualized instance, or a container.
    """
    class Permissions(object):
        customer_path = 'cloud_project_membership__project__customer'
        project_path = 'cloud_project_membership__project'
        project_group_path = 'cloud_project_membership__project__project_groups'

    class States(object):
        PROVISIONING_SCHEDULED = 1
        PROVISIONING = 2

        ONLINE = 3
        OFFLINE = 4

        STARTING_SCHEDULED = 5
        STARTING = 6

        STOPPING_SCHEDULED = 7
        STOPPING = 8

        ERRED = 9

        DELETION_SCHEDULED = 10
        DELETING = 11

        RESIZING_SCHEDULED = 13
        RESIZING = 14

        RESTARTING_SCHEDULED = 15
        RESTARTING = 16

        CHOICES = (
            (PROVISIONING_SCHEDULED, 'Provisioning Scheduled'),
            (PROVISIONING, 'Provisioning'),

            (ONLINE, 'Online'),
            (OFFLINE, 'Offline'),

            (STARTING_SCHEDULED, 'Starting Scheduled'),
            (STARTING, 'Starting'),

            (STOPPING_SCHEDULED, 'Stopping Scheduled'),
            (STOPPING, 'Stopping'),

            (ERRED, 'Erred'),

            (DELETION_SCHEDULED, 'Deletion Scheduled'),
            (DELETING, 'Deleting'),

            (RESIZING_SCHEDULED, 'Resizing Scheduled'),
            (RESIZING, 'Resizing'),

            (RESTARTING_SCHEDULED, 'Restarting Scheduled'),
            (RESTARTING, 'Restarting'),

        )

        # Stable instances are the ones for which
        # no tasks are scheduled or are in progress

        STABLE_STATES = set([ONLINE, OFFLINE, ERRED])
        UNSTABLE_STATES = set([
            s for (s, _) in CHOICES
            if s not in STABLE_STATES
        ])

    # This needs to be inlined in order to set on_delete
    cloud_project_membership = models.ForeignKey(CloudProjectMembership, related_name='+', on_delete=models.PROTECT)
    # XXX: ideally these fields have to be added somewhere in iaas.backup module
    backups = ct_generic.GenericRelation('backup.Backup')
    backup_schedules = ct_generic.GenericRelation('backup.BackupSchedule')

    hostname = models.CharField(max_length=80)
    template = models.ForeignKey(Template, related_name='+')
    external_ips = models.GenericIPAddressField(null=True, blank=True, protocol='IPv4')
    internal_ips = models.GenericIPAddressField(null=True, blank=True, protocol='IPv4')
    start_time = models.DateTimeField(blank=True, null=True)

    state = FSMIntegerField(
        default=States.PROVISIONING_SCHEDULED, max_length=1, choices=States.CHOICES,
        help_text="WARNING! Should not be changed manually unless you really know what you are doing."
    )

    # fields, defined by flavor
    cores = models.PositiveSmallIntegerField(help_text='Number of cores in a VM')
    ram = models.PositiveIntegerField(help_text='Memory size in MiB')

    # fields, defined by ssh public key
    key_name = models.CharField(max_length=50, blank=True)
    key_fingerprint = models.CharField(max_length=47, blank=True)

    # OpenStack backend specific fields
    backend_id = models.CharField(max_length=255, blank=True)
    system_volume_id = models.CharField(max_length=255, blank=True)
    system_volume_size = models.PositiveIntegerField(help_text='Root disk size in MiB')
    data_volume_id = models.CharField(max_length=255, blank=True)
    data_volume_size = models.PositiveIntegerField(default=20 * 1024, help_text='Data disk size in MiB')

    # Services specific fields
    agreed_sla = models.DecimalField(max_digits=6, decimal_places=4, null=True, blank=True)

    @transition(field=state, source=States.PROVISIONING_SCHEDULED, target=States.PROVISIONING)
    def begin_provisioning(self):
        pass

    @transition(field=state, source=[States.PROVISIONING, States.STOPPING, States.RESIZING], target=States.OFFLINE)
    def set_offline(self):
        pass

    @transition(field=state, source=States.OFFLINE, target=States.STARTING_SCHEDULED)
    def schedule_starting(self):
        pass

    @transition(field=state, source=States.STARTING_SCHEDULED, target=States.STARTING)
    def begin_starting(self):
        pass

    @transition(field=state, source=[States.STARTING, States.PROVISIONING, States.RESTARTING], target=States.ONLINE)
    def set_online(self):
        pass

    @transition(field=state, source=States.ONLINE, target=States.STOPPING_SCHEDULED)
    def schedule_stopping(self):
        pass

    @transition(field=state, source=States.STOPPING_SCHEDULED, target=States.STOPPING)
    def begin_stopping(self):
        pass

    @transition(field=state, source=States.OFFLINE, target=States.DELETION_SCHEDULED)
    def schedule_deletion(self):
        pass

    @transition(field=state, source=States.DELETION_SCHEDULED, target=States.DELETING)
    def begin_deleting(self):
        pass

    @transition(field=state, source=States.OFFLINE, target=States.RESIZING_SCHEDULED)
    def schedule_resizing(self):
        pass

    @transition(field=state, source=States.RESIZING_SCHEDULED, target=States.RESIZING)
    def begin_resizing(self):
        pass

    @transition(field=state, source=States.RESIZING, target=States.OFFLINE)
    def set_resized(self):
        pass

    @transition(field=state, source=States.ONLINE, target=States.RESTARTING_SCHEDULED)
    def schedule_restarting(self):
        pass

    @transition(field=state, source=States.RESTARTING_SCHEDULED, target=States.RESTARTING)
    def begin_restarting(self):
        pass

    @transition(field=state, source=States.RESTARTING, target=States.ONLINE)
    def set_restarted(self):
        pass


    @transition(field=state, source='*', target=States.ERRED)
    def set_erred(self):
        pass

    def __str__(self):
        return '%(name)s - %(status)s' % {
            'name': self.hostname,
            'status': self.get_state_display(),
        }

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
                setup_fee=template_license.setup_fee,
                monthly_fee=template_license.monthly_fee,
            )

    def save(self, *args, **kwargs):
        created = self.pk is None
        super(Instance, self).save(*args, **kwargs)
        if created:
            self._init_instance_licenses()


@python_2_unicode_compatible
class InstanceSlaHistory(models.Model):
    period = models.CharField(max_length=10)
    instance = models.ForeignKey(Instance, related_name='slas')
    value = models.DecimalField(max_digits=11, decimal_places=4, null=True, blank=True)

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
class TemplateLicense(core_models.UuidMixin, models.Model):
    class Services(object):
        IAAS = 'IaaS'
        PAAS = 'PaaS'
        SAAS = 'SaaS'
        BPAAS = 'BPaaS'

    SERVICE_TYPES = (
        (Services.IAAS, 'IaaS'), (Services.PAAS, 'PaaS'), (Services.SAAS, 'SaaS'), (Services.BPAAS, 'BPaaS'))

    name = models.CharField(max_length=255)
    license_type = models.CharField(max_length=127)
    templates = models.ManyToManyField(Template, related_name='template_licenses')
    service_type = models.CharField(max_length=10, choices=SERVICE_TYPES)
    setup_fee = models.DecimalField(max_digits=7, decimal_places=3, null=True, blank=True,
                                    validators=[MinValueValidator(Decimal('0.1')),
                                                MaxValueValidator(Decimal('1000.0'))])
    monthly_fee = models.DecimalField(max_digits=7, decimal_places=3, null=True, blank=True,
                                      validators=[MinValueValidator(Decimal('0.1')),
                                                  MaxValueValidator(Decimal('1000.0'))])

    def __str__(self):
        return '%s - %s' % (self.license_type, self.name)

    def get_projects(self):
        return structure_models.Project.objects.filter(
            clouds__images__template__template_licenses=self)

    def get_projects_groups(self):
        return structure_models.ProjectGroup.objects.filter(
            projects__clouds__images__template__template_licenses=self)


@python_2_unicode_compatible
class InstanceLicense(core_models.UuidMixin, models.Model):
    template_license = models.ForeignKey(TemplateLicense, related_name='instance_licenses')
    instance = models.ForeignKey(Instance, related_name='instance_licenses')
    setup_fee = models.DecimalField(max_digits=7, decimal_places=3, null=True, blank=True,
                                    validators=[MinValueValidator(Decimal('0.1')),
                                                MaxValueValidator(Decimal('1000.0'))])
    monthly_fee = models.DecimalField(max_digits=7, decimal_places=3, null=True, blank=True,
                                      validators=[MinValueValidator(Decimal('0.1')),
                                                  MaxValueValidator(Decimal('1000.0'))])

    class Permissions(object):
        customer_path = 'instance__cloud_project_membership__project__customer'
        project_path = 'instance__cloud_project_membership__project'
        project_group_path = 'instance__cloud_project_membership__project__project_groups'

    def __str__(self):
        return 'License: %s for %s' % (self.template_license, self.instance)


@python_2_unicode_compatible
class SecurityGroup(core_models.UuidMixin,
                    core_models.DescribableMixin,
                    CloudProjectMember,
                    models.Model):

    class Permissions(object):
        customer_path = 'cloud_project_membership__project__customer'
        project_path = 'cloud_project_membership__project'
        project_group_path = 'cloud_project_membership__project__project_groups'

    """
    This class contains OpenStack security groups.
    """
    name = models.CharField(max_length=127)

    # OpenStack backend specific fields
    backend_id = models.CharField(max_length=128, blank=True,
                                  help_text='Reference to a SecurityGroup in a remote cloud')

    def __str__(self):
        return self.name


@python_2_unicode_compatible
class SecurityGroupRule(models.Model):

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
    # TODO: Consider protocol dependent to/from_port fields validation
    # TODO: Validate that from_port <= to_port
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

    public_ip = models.IPAddressField(null=False)
    private_ip = models.IPAddressField(null=False)
    project = models.ForeignKey(structure_models.Project, related_name='ip_mappings')
