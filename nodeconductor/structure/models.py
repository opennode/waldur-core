from __future__ import unicode_literals

import yaml
import logging

from django.core.validators import MaxLengthValidator
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import models
from django.db import transaction
from django.db.models import Q
from django.utils.encoding import python_2_unicode_compatible
from model_utils.models import TimeStampedModel
from polymorphic import PolymorphicModel
from django_fsm import FSMIntegerField
from django_fsm import transition

from nodeconductor.core import models as core_models
from nodeconductor.quotas import models as quotas_models
from nodeconductor.events.log import EventLoggableMixin
from nodeconductor.billing.backend import BillingBackend
from nodeconductor.structure.signals import structure_role_granted, structure_role_revoked


logger = logging.getLogger(__name__)


@python_2_unicode_compatible
class Customer(core_models.UuidMixin,
               core_models.NameMixin,
               quotas_models.QuotaModelMixin,
               EventLoggableMixin,
               TimeStampedModel):
    class Permissions(object):
        customer_path = 'self'
        project_path = 'projects'
        project_group_path = 'project_groups'

    native_name = models.CharField(max_length=160, default='', blank=True)
    abbreviation = models.CharField(max_length=8, blank=True)
    contact_details = models.TextField(blank=True, validators=[MaxLengthValidator(500)])

    billing_backend_id = models.CharField(max_length=255, blank=True)
    balance = models.DecimalField(max_digits=9, decimal_places=3, null=True, blank=True)

    QUOTAS_NAMES = ['nc_project_count', 'nc_resource_count', 'nc_user_count']

    def get_billing_backend(self):
        return BillingBackend(self)

    def get_event_log_fields(self):
        return ('uuid', 'name', 'abbreviation', 'contact_details')

    def add_user(self, user, role_type):
        UserGroup = get_user_model().groups.through

        with transaction.atomic():
            role = self.roles.get(role_type=role_type)

            membership, created = UserGroup.objects.get_or_create(
                user=user,
                group=role.permission_group,
            )

            if created:
                structure_role_granted.send(
                    sender=Customer,
                    structure=self,
                    user=user,
                    role=role_type,
                )

            return membership, created

    def remove_user(self, user, role_type=None):
        UserGroup = get_user_model().groups.through

        with transaction.atomic():
            memberships = UserGroup.objects.filter(
                group__customerrole__customer=self,
                user=user,
            )

            if role_type is not None:
                memberships = memberships.filter(group__customerrole__role_type=role_type)

            for membership in memberships.iterator():
                role = membership.group.customerrole

                structure_role_revoked.send(
                    sender=Customer,
                    structure=self,
                    user=membership.user,
                    role=role.role_type,
                )

                membership.delete()

    def has_user(self, user, role_type=None):
        queryset = self.roles.filter(permission_group__user=user)

        if role_type is not None:
            queryset = queryset.filter(role_type=role_type)

        return queryset.exists()

    def get_owners(self):
        return self.roles.get(role_type=CustomerRole.OWNER).permission_group.user_set

    def get_users(self):
        """ Return all connected to customer users """
        return get_user_model().objects.filter(
            Q(groups__customerrole__customer=self) |
            Q(groups__projectrole__project__customer=self) |
            Q(groups__projectgrouprole__project_group__customer=self))

    def can_user_update_quotas(self, user):
        return user.is_staff

    def __str__(self):
        return '%(name)s (%(abbreviation)s)' % {
            'name': self.name,
            'abbreviation': self.abbreviation
        }


@python_2_unicode_compatible
class CustomerRole(models.Model):
    class Meta(object):
        unique_together = ('customer', 'role_type')

    OWNER = 0

    TYPE_CHOICES = (
        (OWNER, 'Owner'),
    )

    ROLE_TO_NAME = {
        OWNER: 'owner',
    }

    NAME_TO_ROLE = dict((v, k) for k, v in ROLE_TO_NAME.items())

    customer = models.ForeignKey(Customer, related_name='roles')
    role_type = models.SmallIntegerField(choices=TYPE_CHOICES)
    permission_group = models.OneToOneField(Group)

    def __str__(self):
        return self.get_role_type_display()


@python_2_unicode_compatible
class ProjectRole(core_models.UuidMixin, models.Model):
    class Meta(object):
        unique_together = ('project', 'role_type')

    ADMINISTRATOR = 0
    MANAGER = 1

    TYPE_CHOICES = (
        (ADMINISTRATOR, 'Administrator'),
        (MANAGER, 'Manager'),
    )

    project = models.ForeignKey('structure.Project', related_name='roles')
    role_type = models.SmallIntegerField(choices=TYPE_CHOICES)
    permission_group = models.OneToOneField(Group)

    def __str__(self):
        return self.get_role_type_display()


@python_2_unicode_compatible
class Project(core_models.DescribableMixin,
              core_models.UuidMixin,
              core_models.NameMixin,
              quotas_models.QuotaModelMixin,
              EventLoggableMixin,
              TimeStampedModel):
    class Permissions(object):
        customer_path = 'customer'
        project_path = 'self'
        project_group_path = 'project_groups'

    QUOTAS_NAMES = ['vcpu', 'ram', 'storage', 'max_instances']

    customer = models.ForeignKey(Customer, related_name='projects', on_delete=models.PROTECT)

    def add_user(self, user, role_type):
        UserGroup = get_user_model().groups.through

        with transaction.atomic():

            role = self.roles.get(role_type=role_type)

            membership, created = UserGroup.objects.get_or_create(
                user=user,
                group=role.permission_group,
            )

            if created:
                structure_role_granted.send(
                    sender=Project,
                    structure=self,
                    user=user,
                    role=role_type,
                )

            return membership, created

    def remove_user(self, user, role_type=None):
        UserGroup = get_user_model().groups.through

        with transaction.atomic():
            memberships = UserGroup.objects.filter(
                group__projectrole__project=self,
                user=user,
            )

            if role_type is not None:
                memberships = memberships.filter(group__projectrole__role_type=role_type)

            for membership in memberships.iterator():
                role = membership.group.projectrole
                structure_role_revoked.send(
                    sender=Project,
                    structure=self,
                    user=membership.user,
                    role=role.role_type,
                )

                membership.delete()

    def has_user(self, user, role_type=None):
        queryset = self.roles.filter(permission_group__user=user)

        if role_type is not None:
            queryset = queryset.filter(role_type=role_type)

        return queryset.exists()

    def __str__(self):
        return '%(name)s | %(customer)s' % {
            'name': self.name,
            'customer': self.customer.name
        }

    def can_user_update_quotas(self, user):
        return user.is_staff


@python_2_unicode_compatible
class ProjectGroupRole(core_models.UuidMixin, models.Model):
    class Meta(object):
        unique_together = ('project_group', 'role_type')

    MANAGER = 0

    TYPE_CHOICES = (
        (MANAGER, 'Group Manager'),
    )

    project_group = models.ForeignKey('structure.ProjectGroup', related_name='roles')
    role_type = models.SmallIntegerField(choices=TYPE_CHOICES)
    permission_group = models.OneToOneField(Group)

    def __str__(self):
        return self.get_role_type_display()


@python_2_unicode_compatible
class ProjectGroup(core_models.UuidMixin,
                   core_models.DescribableMixin,
                   core_models.NameMixin,
                   EventLoggableMixin,
                   TimeStampedModel):
    """
    Project groups are means to organize customer's projects into arbitrary sets.
    """
    class Permissions(object):
        customer_path = 'customer'
        project_path = 'projects'
        project_group_path = 'self'

    customer = models.ForeignKey(Customer, related_name='project_groups', on_delete=models.PROTECT)
    projects = models.ManyToManyField(Project,
                                      related_name='project_groups')

    def __str__(self):
        return self.name

    def add_user(self, user, role_type):
        UserGroup = get_user_model().groups.through

        with transaction.atomic():
            role = self.roles.get(role_type=role_type)

            membership, created = UserGroup.objects.get_or_create(
                user=user,
                group=role.permission_group,
            )

            if created:
                structure_role_granted.send(
                    sender=ProjectGroup,
                    structure=self,
                    user=user,
                    role=role_type,
                )

            return membership, created

    def remove_user(self, user, role_type=None):
        UserGroup = get_user_model().groups.through

        with transaction.atomic():
            memberships = UserGroup.objects.filter(
                group__projectgrouprole__project_group=self,
                user=user,
            )

            if role_type is not None:
                memberships = memberships.filter(group__projectgrouprole__role_type=role_type)

            for membership in memberships.iterator():
                role = membership.group.projectgrouprole
                structure_role_revoked.send(
                    sender=ProjectGroup,
                    structure=self,
                    user=membership.user,
                    role=role.role_type,
                )

                membership.delete()

    def has_user(self, user, role_type=None):
        queryset = self.roles.filter(permission_group__user=user)

        if role_type is not None:
            queryset = queryset.filter(role_type=role_type)

        return queryset.exists()


@python_2_unicode_compatible
class Service(PolymorphicModel, core_models.UuidMixin,
              core_models.NameMixin, core_models.SynchronizableMixin):

    """ Base service class. Define specific service model as follows:

        .. code-block:: python

            class JiraService(Service):
                projects = 'JiraProjectLink'
                username = models.CharField(max_length=64)
                password = models.CharField(max_length=16)

            class JiraProjectLink(ServiceProjectLink):
                service = 'JiraService'
                backend_id = models.CharField(max_length=255)


            class DigitalOceanService(Service):
                projects = 'DigitalOceanProjectLink'
                auth_token = models.CharField(max_length=64)

            class DigitalOceanProjectLink(ServiceProjectLink):
                QUOTAS_NAMES = ['max_droplets']
                service = 'DigitalOceanService'

        List all services with single query:

        .. code-block:: python

            >>> Service.objects.all()
                [ <JiraService: id 1, name "Main JIRA">,
                  <DigitalOceanService: id 1, name "Production DO Cloud">,
                  <DigitalOceanService: id 2, name "Temp DigitalOcean"> ]
    """

    class Meta(object):
        unique_together = ('customer', 'name', 'polymorphic_ctype')

    class Permissions(object):
        customer_path = 'customer'
        project_path = 'projects'
        project_group_path = 'customer__projects__project_groups'

    customer = models.ForeignKey(Customer, related_name='services')
    projects = NotImplemented

    dummy = models.BooleanField(default=False, help_text='Emulate backend operations')

    def get_backend(self, sp_link=None):
        raise NotImplementedError

    def __str__(self):
        return self.name


@python_2_unicode_compatible
class ServiceProperty(core_models.UuidMixin, core_models.NameMixin, models.Model):
    """ Base service properties like image, flavor, region,
        which are usually used for Resource provisioning.
    """

    class Meta(object):
        abstract = True

    class Permissions(object):
        customer_path = 'service__customer'
        project_path = 'service__projects'
        project_group_path = 'service__projects__project_groups'

    service = NotImplemented
    backend_id = models.CharField(max_length=255)

    def __str__(self):
        return '{0} | {1}'.format(self.service.name, self.name)


@python_2_unicode_compatible
class ServiceProjectLink(core_models.SynchronizableMixin, quotas_models.QuotaModelMixin):
    """ Base service-project link class. See Service class for usage example. """

    class Meta(object):
        abstract = True

    class Permissions(object):
        customer_path = 'service__customer'
        project_path = 'project'
        project_group_path = 'project__project_groups'

    service = NotImplemented
    project = models.ForeignKey(Project)

    def get_quota_parents(self):
        return [self.project]

    def get_backend(self):
        return self.service.get_backend(sp_link=self)

    def __str__(self):
        return '{0} | {1}'.format(self.service.name, self.project.name)


@python_2_unicode_compatible
class Resource(core_models.UuidMixin, core_models.DescribableMixin,
               core_models.NameMixin, TimeStampedModel):

    """ Base resource class. Resource is a provisioned entity of a service,
        for example: a VM in OpenStack or AWS, or a repository in Github.
    """

    class Meta(object):
        abstract = True

    class Permissions(object):
        customer_path = 'service_project_link__project__customer'
        project_path = 'service_project_link__project'
        project_group_path = 'service_project_link__project__project_groups'

    service_project_link = NotImplemented

    def get_backend(self):
        return self.service_project_link.get_backend()

    def __str__(self):
        return self.name


def validate_yaml(value):
    try:
        yaml.load(value)
    except yaml.error.YAMLError:
        raise ValidationError('A valid YAML value is required.')


class VirtualMachineStates(object):
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

    STABLE_STATES = set([ONLINE, OFFLINE])
    UNSTABLE_STATES = set([
        s for (s, _) in CHOICES
        if s not in STABLE_STATES
    ])


class VirtualMachineMixin(models.Model):

    class Meta(object):
        abstract = True

    cores = models.PositiveSmallIntegerField(blank=True, null=True, help_text='Number of cores in a VM')
    ram = models.PositiveIntegerField(blank=True, null=True, help_text='Memory size in MiB')
    disk = models.PositiveIntegerField(blank=True, null=True, help_text='Disk size in MiB')
    bandwidth = models.PositiveIntegerField(blank=True, null=True, help_text='Bandwidth size in MiB')

    start_time = models.DateTimeField(blank=True, null=True)

    user_data = models.TextField(
        blank=True, validators=[validate_yaml],
        help_text='Additional data that will be added to resource on provisioning')

    state = FSMIntegerField(
        default=VirtualMachineStates.PROVISIONING_SCHEDULED,
        choices=VirtualMachineStates.CHOICES,
        help_text="WARNING! Should not be changed manually unless you really know what you are doing.",
        max_length=1)

    @transition(field=state,
                source=VirtualMachineStates.PROVISIONING_SCHEDULED,
                target=VirtualMachineStates.PROVISIONING)
    def begin_provisioning(self):
        pass

    @transition(field=state,
                source=[VirtualMachineStates.PROVISIONING, VirtualMachineStates.STOPPING, VirtualMachineStates.RESIZING],
                target=VirtualMachineStates.OFFLINE)
    def set_offline(self):
        pass

    @transition(field=state,
                source=VirtualMachineStates.OFFLINE,
                target=VirtualMachineStates.STARTING_SCHEDULED)
    def schedule_starting(self):
        pass

    @transition(field=state,
                source=VirtualMachineStates.STARTING_SCHEDULED,
                target=VirtualMachineStates.STARTING)
    def begin_starting(self):
        pass

    @transition(field=state,
                source=[VirtualMachineStates.STARTING, VirtualMachineStates.PROVISIONING, VirtualMachineStates.RESTARTING],
                target=VirtualMachineStates.ONLINE)
    def set_online(self):
        pass

    @transition(field=state,
                source=VirtualMachineStates.ONLINE,
                target=VirtualMachineStates.STOPPING_SCHEDULED)
    def schedule_stopping(self):
        pass

    @transition(field=state,
                source=VirtualMachineStates.STOPPING_SCHEDULED,
                target=VirtualMachineStates.STOPPING)
    def begin_stopping(self):
        pass

    @transition(field=state,
                source=VirtualMachineStates.OFFLINE,
                target=VirtualMachineStates.DELETION_SCHEDULED)
    def schedule_deletion(self):
        pass

    @transition(field=state,
                source=VirtualMachineStates.DELETION_SCHEDULED,
                target=VirtualMachineStates.DELETING)
    def begin_deleting(self):
        pass

    @transition(field=state,
                source=VirtualMachineStates.OFFLINE,
                target=VirtualMachineStates.RESIZING_SCHEDULED)
    def schedule_resizing(self):
        pass

    @transition(field=state,
                source=VirtualMachineStates.RESIZING_SCHEDULED,
                target=VirtualMachineStates.RESIZING)
    def begin_resizing(self):
        pass

    @transition(field=state,
                source=VirtualMachineStates.RESIZING,
                target=VirtualMachineStates.OFFLINE)
    def set_resized(self):
        pass

    @transition(field=state,
                source=VirtualMachineStates.ONLINE,
                target=VirtualMachineStates.RESTARTING_SCHEDULED)
    def schedule_restarting(self):
        pass

    @transition(field=state,
                source=VirtualMachineStates.RESTARTING_SCHEDULED,
                target=VirtualMachineStates.RESTARTING)
    def begin_restarting(self):
        pass

    @transition(field=state,
                source=VirtualMachineStates.RESTARTING,
                target=VirtualMachineStates.ONLINE)
    def set_restarted(self):
        pass

    @transition(field=state,
                source='*',
                target=VirtualMachineStates.ERRED)
    def set_erred(self):
        pass
