from __future__ import unicode_literals

import yaml

from django.apps import apps
from django.core.validators import MaxLengthValidator
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import models, transaction
from django.db.models import Q, F
from django.utils.lru_cache import lru_cache
from django.utils.encoding import python_2_unicode_compatible
from django_fsm import FSMIntegerField
from django_fsm import transition
from model_utils.fields import AutoCreatedField
from model_utils.models import TimeStampedModel
from model_utils import FieldTracker
from jsonfield import JSONField

from nodeconductor.core import models as core_models
from nodeconductor.core.tasks import send_task
from nodeconductor.quotas import models as quotas_models
from nodeconductor.logging.log import LoggableMixin
from nodeconductor.structure.managers import StructureManager, filter_queryset_for_user
from nodeconductor.structure.signals import structure_role_granted, structure_role_revoked
from nodeconductor.structure.signals import customer_account_credited, customer_account_debited
from nodeconductor.structure.images import ImageModelMixin
from nodeconductor.structure import SupportedServices


def set_permissions_for_model(model, **kwargs):
    class Permissions(object):
        pass
    for key, value in kwargs.items():
        setattr(Permissions, key, value)

    setattr(model, 'Permissions', Permissions)


class StructureModel(models.Model):
    """ Generic structure model.
        Provides transparent interaction with base entities and relations like customer.
    """

    objects = StructureManager()

    class Meta(object):
        abstract = True

    def __getattr__(self, name):
        # add additional properties to the object according to defined Permissions class
        fields = ('customer', 'project')
        if name in fields:
            try:
                path = getattr(self.Permissions, name + '_path')
            except AttributeError:
                pass
            else:
                if not path == 'self' and '__' in path:
                    return reduce(getattr, path.split('__'), self)

        raise AttributeError(
            "'%s' object has no attribute '%s'" % (self._meta.object_name, name))


@python_2_unicode_compatible
class Customer(core_models.UuidMixin,
               core_models.NameMixin,
               quotas_models.QuotaModelMixin,
               LoggableMixin,
               ImageModelMixin,
               TimeStampedModel,
               StructureModel):
    class Permissions(object):
        customer_path = 'self'
        project_path = 'projects'
        project_group_path = 'project_groups'

    native_name = models.CharField(max_length=160, default='', blank=True)
    abbreviation = models.CharField(max_length=8, blank=True)
    contact_details = models.TextField(blank=True, validators=[MaxLengthValidator(500)])

    registration_code = models.CharField(max_length=160, default='', blank=True)

    billing_backend_id = models.CharField(max_length=255, blank=True)
    balance = models.DecimalField(max_digits=9, decimal_places=3, null=True, blank=True)

    QUOTAS_NAMES = [
        'nc_project_count',
        'nc_resource_count',
        'nc_user_count',
        'nc_service_project_link_count',
        'nc_service_count'
    ]
    GLOBAL_COUNT_QUOTA_NAME = 'nc_global_customer_count'

    def get_log_fields(self):
        return ('uuid', 'name', 'abbreviation', 'contact_details')

    def credit_account(self, amount):
        # Increase customer's balance by specified amount
        new_balance = (self.balance or 0) + amount
        self._meta.model.objects.filter(uuid=self.uuid).update(
            balance=new_balance if self.balance is None else F('balance') + amount)

        self.balance = new_balance
        BalanceHistory.objects.create(customer=self, amount=self.balance)
        customer_account_credited.send(sender=Customer, instance=self, amount=float(amount))

    def debit_account(self, amount):
        # Reduce customer's balance at specified amount
        new_balance = (self.balance or 0) - amount
        self._meta.model.objects.filter(uuid=self.uuid).update(
            balance=new_balance if self.balance is None else F('balance') - amount)

        self.balance = new_balance
        BalanceHistory.objects.create(customer=self, amount=self.balance)
        customer_account_debited.send(sender=Customer, instance=self, amount=float(amount))

        # Fully prepaid mode
        # TODO: Introduce threshold value to allow over-usage
        if new_balance <= 0:
            send_task('structure', 'stop_customer_resources')(self.uuid.hex)

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

    @classmethod
    def get_permitted_objects_uuids(cls, user):
        if user.is_staff:
            customer_queryset = cls.objects.all()
        else:
            customer_queryset = cls.objects.filter(
                roles__permission_group__user=user, roles__role_type=CustomerRole.OWNER)
        return {'customer_uuid': filter_queryset_for_user(customer_queryset, user).values_list('uuid', flat=True)}

    def __str__(self):
        return '%(name)s (%(abbreviation)s)' % {
            'name': self.name,
            'abbreviation': self.abbreviation
        }


class BalanceHistory(models.Model):
    customer = models.ForeignKey(Customer)
    created = AutoCreatedField()
    amount = models.DecimalField(max_digits=9, decimal_places=3)


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
              core_models.DescendantMixin,
              quotas_models.QuotaModelMixin,
              LoggableMixin,
              TimeStampedModel,
              StructureModel):
    class Permissions(object):
        customer_path = 'customer'
        project_path = 'self'
        project_group_path = 'project_groups'

    QUOTAS_NAMES = ['nc_resource_count', 'nc_service_project_link_count']
    GLOBAL_COUNT_QUOTA_NAME = 'nc_global_project_count'

    customer = models.ForeignKey(Customer, related_name='projects', on_delete=models.PROTECT)
    tracker = FieldTracker()

    # XXX: Hack for gcloud and logging
    @property
    def project_group(self):
        return self.project_groups.first()

    @property
    def full_name(self):
        project_group = self.project_group
        name = (project_group.name + ' / ' if project_group else '') + self.name
        return name

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

            self.remove_memberships(memberships)

    def remove_all_users(self):
        UserGroup = get_user_model().groups.through

        with transaction.atomic():
            memberships = UserGroup.objects.filter(group__projectrole__project=self)
            self.remove_memberships(memberships)

    def remove_memberships(self, memberships):
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

    def get_users(self):
        return get_user_model().objects.filter(groups__projectrole__project=self)

    def __str__(self):
        return '%(name)s | %(customer)s' % {
            'name': self.name,
            'customer': self.customer.name
        }

    def can_user_update_quotas(self, user):
        return user.is_staff

    def get_log_fields(self):
        return ('uuid', 'customer', 'name', 'project_group')

    @classmethod
    def get_permitted_objects_uuids(cls, user):
        return {'project_uuid': filter_queryset_for_user(cls.objects.all(), user).values_list('uuid', flat=True)}

    def get_parents(self):
        return [self.customer]

    def get_links(self):
        """
        Get all service project links connected to current project
        """
        return [link for model in SupportedServices.get_service_models().values()
                     for link in model['service_project_link'].objects.filter(project=self)]


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
                   core_models.DescendantMixin,
                   quotas_models.QuotaModelMixin,
                   LoggableMixin,
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

    tracker = FieldTracker()

    GLOBAL_COUNT_QUOTA_NAME = 'nc_global_project_group_count'

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

    def get_log_fields(self):
        return ('uuid', 'customer', 'name')

    def get_parents(self):
        return [self.customer]

    @classmethod
    def get_permitted_objects_uuids(cls, user):
        return {'project_group_uuid': filter_queryset_for_user(cls.objects.all(), user).values_list('uuid', flat=True)}


@python_2_unicode_compatible
class ServiceSettings(core_models.UuidMixin,
                      core_models.NameMixin,
                      core_models.SynchronizableMixin,
                      LoggableMixin):

    class Meta:
        verbose_name = "Service settings"
        verbose_name_plural = "Service settings"

    class Permissions(object):
        customer_path = 'customer'
        extra_query = dict(shared=True)

    customer = models.ForeignKey(Customer, related_name='service_settings', blank=True, null=True)
    backend_url = models.URLField(max_length=200, blank=True, null=True)
    username = models.CharField(max_length=100, blank=True, null=True)
    password = models.CharField(max_length=100, blank=True, null=True)
    token = models.CharField(max_length=255, blank=True, null=True)
    certificate = models.FileField(upload_to='certs', blank=True, null=True)
    type = models.SmallIntegerField(choices=SupportedServices.Types.CHOICES)

    options = JSONField(blank=True, help_text='Extra options')

    shared = models.BooleanField(default=False, help_text='Anybody can use it')
    # TODO: Implement demo mode instead of dummy mode (NC-900)
    dummy = models.BooleanField(default=False, help_text='Emulate backend operations')

    def get_backend(self, **kwargs):
        return SupportedServices.get_service_backend(self.type)(self, **kwargs)

    def __str__(self):
        return '%s (%s)' % (self.name, self.get_type_display())

    def get_log_fields(self):
        return ('uuid', 'name', 'customer')

    def _get_log_context(self, entity_name):
        context = super(ServiceSettings, self)._get_log_context(entity_name)
        context['service_settings_type'] = self.get_type_display()
        return context


@python_2_unicode_compatible
class Service(core_models.SerializableAbstractMixin,
              core_models.UuidMixin,
              core_models.NameMixin,
              LoggableMixin,
              StructureModel):
    """ Base service class. """

    class Meta(object):
        abstract = True
        unique_together = ('customer', 'settings')

    class Permissions(object):
        customer_path = 'customer'
        project_path = 'projects'
        project_group_path = 'customer__projects__project_groups'

    settings = models.ForeignKey(ServiceSettings)
    customer = models.ForeignKey(Customer)
    available_for_all = models.BooleanField(
        default=False,
        help_text="Service will be automatically added to all customers projects if it is available for all"
    )
    projects = NotImplemented

    def get_backend(self, **kwargs):
        return self.settings.get_backend(**kwargs)

    def __str__(self):
        return self.name

    @classmethod
    @lru_cache(maxsize=1)
    def get_all_models(cls):
        return [model for model in apps.get_models() if issubclass(model, cls)]

    @classmethod
    @lru_cache(maxsize=1)
    def get_url_name(cls):
        """ This name will be used by generic relationships to membership model for URL creation """
        return cls._meta.app_label

    def get_log_fields(self):
        return ('uuid', 'name', 'customer')

    def _get_log_context(self, entity_name):
        context = super(Service, self)._get_log_context(entity_name)
        context['service_type'] = SupportedServices.get_name_for_model(self)
        return context

    def get_service_project_links(self):
        """
        Generic method for getting queryset of service project links related to current service
        """
        return self.projects.through.objects.filter(service=self)


class BaseServiceProperty(core_models.UuidMixin, core_models.NameMixin, models.Model):
    """ Base service properties like image, flavor, region,
        which are usually used for Resource provisioning.
    """

    class Meta(object):
        abstract = True

    @classmethod
    @lru_cache(maxsize=1)
    def get_url_name(cls):
        """ This name will be used by generic relationships to membership model for URL creation """
        return '{}-{}'.format(cls._meta.app_label, cls.__name__.lower())


@python_2_unicode_compatible
class ServiceProperty(BaseServiceProperty):

    class Meta(object):
        abstract = True
        unique_together = ('settings', 'backend_id')

    settings = models.ForeignKey(ServiceSettings, related_name='+')
    backend_id = models.CharField(max_length=255, db_index=True)

    def __str__(self):
        return '{0} | {1}'.format(self.name, self.settings)


@python_2_unicode_compatible
class GeneralServiceProperty(BaseServiceProperty):
    """
    Service property which is not connected to settings
    """

    class Meta(object):
        abstract = True

    backend_id = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name


@python_2_unicode_compatible
class ServiceProjectLink(core_models.SerializableAbstractMixin,
                         core_models.SynchronizableMixin,
                         core_models.DescendantMixin,
                         LoggableMixin,
                         StructureModel):
    """ Base service-project link class. See Service class for usage example. """

    class Meta(object):
        abstract = True

    class Permissions(object):
        customer_path = 'service__customer'
        project_path = 'project'
        project_group_path = 'project__project_groups'

    service = NotImplemented
    project = models.ForeignKey(Project)

    def get_backend(self, **kwargs):
        return self.service.get_backend(**kwargs)

    @classmethod
    @lru_cache(maxsize=1)
    def get_all_models(cls):
        return [model for model in apps.get_models() if issubclass(model, cls)]

    @classmethod
    @lru_cache(maxsize=1)
    def get_url_name(cls):
        """ This name will be used by generic relationships to membership model for URL creation """
        return cls._meta.app_label + '-spl'

    def get_log_fields(self):
        return ('project', 'service',)

    def get_parents(self):
        return [self.project, self.service]

    def __str__(self):
        return '{0} | {1}'.format(self.service.name, self.project.name)


def validate_yaml(value):
    try:
        yaml.load(value)
    except yaml.error.YAMLError:
        raise ValidationError('A valid YAML value is required.')


class BaseVirtualMachineMixin(models.Model):
    key_name = models.CharField(max_length=50, blank=True)
    key_fingerprint = models.CharField(max_length=47, blank=True)

    user_data = models.TextField(
        blank=True, validators=[validate_yaml],
        help_text='Additional data that will be added to instance on provisioning')

    class Meta(object):
        abstract = True


class VirtualMachineMixin(BaseVirtualMachineMixin):
    # This extra class required in order not to get into a mess with current iaas implementation
    cores = models.PositiveSmallIntegerField(default=0, help_text='Number of cores in a VM')
    ram = models.PositiveIntegerField(default=0, help_text='Memory size in MiB')
    disk = models.PositiveIntegerField(default=0, help_text='Disk size in MiB')

    class Meta(object):
        abstract = True


class PaidResource(models.Model):
    """ Extend Resource model with methods to track usage cost and handle orders """

    billing_backend_id = models.CharField(max_length=255, blank=True, help_text='ID of a resource in backend')
    last_usage_update_time = models.DateTimeField(blank=True, null=True)

    @classmethod
    @lru_cache(maxsize=1)
    def get_all_models(cls):
        return [model for model in Resource.get_all_models() if issubclass(model, cls)]

    class Meta(object):
        abstract = True


@python_2_unicode_compatible
class Resource(core_models.UuidMixin,
               core_models.DescribableMixin,
               core_models.NameMixin,
               core_models.ErrorMessageMixin,
               core_models.SerializableAbstractMixin,
               core_models.DescendantMixin,
               LoggableMixin,
               TimeStampedModel,
               StructureModel):

    """ Base resource class. Resource is a provisioned entity of a service,
        for example: a VM in OpenStack or AWS, or a repository in Github.
    """

    class Meta(object):
        abstract = True

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
        # tasks are scheduled or are in progress

        STABLE_STATES = set([ONLINE, OFFLINE])
        UNSTABLE_STATES = set([
            s for (s, _) in CHOICES
            if s not in STABLE_STATES
        ])

    class Permissions(object):
        customer_path = 'service_project_link__project__customer'
        project_path = 'service_project_link__project'
        project_group_path = 'service_project_link__project__project_groups'

    service_project_link = NotImplemented
    backend_id = models.CharField(max_length=255, blank=True)

    start_time = models.DateTimeField(blank=True, null=True)
    state = FSMIntegerField(
        default=States.PROVISIONING_SCHEDULED,
        choices=States.CHOICES,
        help_text="WARNING! Should not be changed manually unless you really know what you are doing.",
        max_length=1)

    def get_backend(self, **kwargs):
        return self.service_project_link.get_backend(**kwargs)

    def get_cost(self, start_date, end_date):
        raise NotImplementedError(
            "Please refer to nodeconductor.billing.tasks.debit_customers while implementing it")

    @classmethod
    @lru_cache(maxsize=1)
    def get_all_models(cls):
        return [model for model in apps.get_models() if issubclass(model, cls)]

    @classmethod
    @lru_cache(maxsize=1)
    def get_url_name(cls):
        """ This name will be used by generic relationships to membership model for URL creation """
        return '{}-{}'.format(cls._meta.app_label, cls.__name__.lower())

    def get_log_fields(self):
        return ('uuid', 'name', 'service_project_link')

    def _get_log_context(self, entity_name):
        context = super(Resource, self)._get_log_context(entity_name)
        context['resource_type'] = SupportedServices.get_name_for_model(self)
        return context

    def get_parents(self):
        return [self.service_project_link]

    def __str__(self):
        return self.name

    @transition(field=state,
                source=States.PROVISIONING_SCHEDULED,
                target=States.PROVISIONING)
    def begin_provisioning(self):
        pass

    @transition(field=state,
                source=[States.PROVISIONING, States.STOPPING, States.RESIZING],
                target=States.OFFLINE)
    def set_offline(self):
        pass

    @transition(field=state,
                source=States.OFFLINE,
                target=States.STARTING_SCHEDULED)
    def schedule_starting(self):
        pass

    @transition(field=state,
                source=States.STARTING_SCHEDULED,
                target=States.STARTING)
    def begin_starting(self):
        pass

    @transition(field=state,
                source=[States.STARTING, States.PROVISIONING, States.RESTARTING],
                target=States.ONLINE)
    def set_online(self):
        pass

    @transition(field=state,
                source=States.ONLINE,
                target=States.STOPPING_SCHEDULED)
    def schedule_stopping(self):
        pass

    @transition(field=state,
                source=States.STOPPING_SCHEDULED,
                target=States.STOPPING)
    def begin_stopping(self):
        pass

    @transition(field=state,
                source=States.OFFLINE,
                target=States.DELETION_SCHEDULED)
    def schedule_deletion(self):
        pass

    @transition(field=state,
                source=States.DELETION_SCHEDULED,
                target=States.DELETING)
    def begin_deleting(self):
        pass

    @transition(field=state,
                source=States.OFFLINE,
                target=States.RESIZING_SCHEDULED)
    def schedule_resizing(self):
        pass

    @transition(field=state,
                source=States.RESIZING_SCHEDULED,
                target=States.RESIZING)
    def begin_resizing(self):
        pass

    @transition(field=state,
                source=States.RESIZING,
                target=States.OFFLINE)
    def set_resized(self):
        pass

    @transition(field=state,
                source=States.ONLINE,
                target=States.RESTARTING_SCHEDULED)
    def schedule_restarting(self):
        pass

    @transition(field=state,
                source=States.RESTARTING_SCHEDULED,
                target=States.RESTARTING)
    def begin_restarting(self):
        pass

    @transition(field=state,
                source=States.RESTARTING,
                target=States.ONLINE)
    def set_restarted(self):
        pass

    @transition(field=state,
                source='*',
                target=States.ERRED)
    def set_erred(self):
        pass
