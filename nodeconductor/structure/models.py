from __future__ import unicode_literals

import yaml
import itertools

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MaxLengthValidator
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q, F
from django.utils.encoding import python_2_unicode_compatible
from django.utils.lru_cache import lru_cache
from django.utils.translation import ugettext_lazy as _
from django_fsm import FSMIntegerField
from django_fsm import transition
from jsonfield import JSONField
from model_utils import FieldTracker
from model_utils.models import TimeStampedModel
from model_utils.fields import AutoCreatedField
from taggit.managers import TaggableManager


from nodeconductor.core import models as core_models
from nodeconductor.core.models import CoordinatesMixin, AbstractFieldTracker
from nodeconductor.core.tasks import send_task
from nodeconductor.monitoring.models import MonitoringModelMixin
from nodeconductor.quotas import models as quotas_models, fields as quotas_fields
from nodeconductor.logging.loggers import LoggableMixin
from nodeconductor.structure.managers import StructureManager, filter_queryset_for_user, ServiceSettingsManager
from nodeconductor.structure.signals import structure_role_granted, structure_role_revoked
from nodeconductor.structure.signals import customer_account_credited, customer_account_debited
from nodeconductor.structure.images import ImageModelMixin
from nodeconductor.structure import SupportedServices
from nodeconductor.structure.utils import get_coordinates_by_ip


def validate_service_type(service_type):
    from django.core.exceptions import ValidationError
    if not SupportedServices.has_service_type(service_type):
        raise ValidationError('Invalid service type')


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
               core_models.DescendantMixin,
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

    GLOBAL_COUNT_QUOTA_NAME = 'nc_global_customer_count'

    class Quotas(quotas_models.QuotaModelMixin.Quotas):
        nc_project_count = quotas_fields.CounterQuotaField(
            target_models=lambda: [Project],
            path_to_scope='customer',
        )
        nc_service_count = quotas_fields.CounterQuotaField(
            target_models=lambda: Service.get_all_models(),
            path_to_scope='customer',
        )
        nc_user_count = quotas_fields.QuotaField()
        nc_resource_count = quotas_fields.CounterQuotaField(
            target_models=lambda: ResourceMixin.get_all_models(),
            path_to_scope='project.customer',
        )
        nc_app_count = quotas_fields.CounterQuotaField(
            target_models=lambda: ResourceMixin.get_app_models(),
            path_to_scope='project.customer',
        )
        nc_vm_count = quotas_fields.CounterQuotaField(
            target_models=lambda: ResourceMixin.get_vm_models(),
            path_to_scope='project.customer',
        )
        nc_private_cloud_count = quotas_fields.CounterQuotaField(
            target_models=lambda: ResourceMixin.get_private_cloud_models(),
            path_to_scope='project.customer',
        )
        nc_service_project_link_count = quotas_fields.CounterQuotaField(
            target_models=lambda: ServiceProjectLink.get_all_models(),
            path_to_scope='project.customer',
        )

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
                membership.delete()

                structure_role_revoked.send(
                    sender=Customer,
                    structure=self,
                    user=membership.user,
                    role=role.role_type,
                )

    def has_user(self, user, role_type=None):
        queryset = self.roles.filter(permission_group__user=user)

        if role_type is not None:
            queryset = queryset.filter(role_type=role_type)

        return queryset.exists()

    def get_owners(self):
        return get_user_model().objects.filter(
            groups__customerrole__customer=self,
            groups__customerrole__role_type=CustomerRole.OWNER
        )

    def get_users(self):
        """ Return all connected to customer users """
        return get_user_model().objects.filter(
            Q(groups__customerrole__customer=self) |
            Q(groups__projectrole__project__customer=self) |
            Q(groups__projectgrouprole__project_group__customer=self)).distinct()

    def can_user_update_quotas(self, user):
        return user.is_staff

    def get_children(self):
        return itertools.chain.from_iterable(
            m.objects.filter(customer=self) for m in [Project] + Service.get_all_models())

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

    GLOBAL_COUNT_QUOTA_NAME = 'nc_global_project_count'

    class Quotas(quotas_models.QuotaModelMixin.Quotas):
        nc_resource_count = quotas_fields.CounterQuotaField(
            target_models=lambda: ResourceMixin.get_all_models(),
            path_to_scope='project',
        )
        nc_app_count = quotas_fields.CounterQuotaField(
            target_models=lambda: ResourceMixin.get_app_models(),
            path_to_scope='project',
        )
        nc_vm_count = quotas_fields.CounterQuotaField(
            target_models=lambda: ResourceMixin.get_vm_models(),
            path_to_scope='project',
        )
        nc_private_cloud_count = quotas_fields.CounterQuotaField(
            target_models=lambda: ResourceMixin.get_private_cloud_models(),
            path_to_scope='project',
        )
        nc_service_project_link_count = quotas_fields.CounterQuotaField(
            target_models=lambda: ServiceProjectLink.get_all_models(),
            path_to_scope='project',
        )

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
            membership.delete()

            structure_role_revoked.send(
                sender=Project,
                structure=self,
                user=membership.user,
                role=role.role_type,
            )

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

    def get_children(self):
        return itertools.chain.from_iterable(
            m.objects.filter(project=self) for m in ServiceProjectLink.get_all_models())

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
                membership.delete()

                structure_role_revoked.send(
                    sender=ProjectGroup,
                    structure=self,
                    user=membership.user,
                    role=role.role_type,
                )

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
class ServiceSettings(quotas_models.ExtendableQuotaModelMixin,
                      core_models.UuidMixin,
                      core_models.NameMixin,
                      core_models.StateMixin,
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
    type = models.CharField(max_length=255, db_index=True, validators=[validate_service_type])
    options = JSONField(default={}, help_text='Extra options', blank=True)
    shared = models.BooleanField(default=False, help_text='Anybody can use it')

    tags = TaggableManager(related_name='+', blank=True)

    # service settings scope - VM that contains service
    content_type = models.ForeignKey(ContentType, null=True)
    object_id = models.PositiveIntegerField(null=True)
    scope = GenericForeignKey('content_type', 'object_id')

    objects = ServiceSettingsManager('scope')

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

    def get_type_display(self):
        return SupportedServices.get_name_for_type(self.type)


@python_2_unicode_compatible
class Service(core_models.SerializableAbstractMixin,
              core_models.UuidMixin,
              core_models.NameMixin,
              core_models.DescendantMixin,
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

    def get_parents(self):
        return [self.settings]

    def get_children(self):
        return itertools.chain.from_iterable(
            m.objects.filter(**{
                'cloud' if 'cloud' in m._meta.get_all_field_names() else 'service': self
            }) for m in ServiceProjectLink.get_all_models())


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
class ServiceProjectLink(quotas_models.QuotaModelMixin,
                         core_models.SerializableAbstractMixin,
                         core_models.DescendantMixin,
                         LoggableMixin,
                         StructureModel):
    """ Base service-project link class. See Service class for usage example. """

    class Meta(object):
        abstract = True
        unique_together = ('service', 'project')

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

    def get_children(self):
        return itertools.chain.from_iterable(
            m.objects.filter(service_project_link=self) for m in
            SupportedServices.get_related_models(self)['resources'])

    def __str__(self):
        return '{0} | {1}'.format(self.service.name, self.project.name)


def validate_yaml(value):
    try:
        yaml.load(value)
    except yaml.error.YAMLError:
        raise ValidationError('A valid YAML value is required.')


# This extra class required in order not to get into a mess with current iaas implementation
class BaseVirtualMachineMixin(models.Model):
    key_name = models.CharField(max_length=50, blank=True)
    key_fingerprint = models.CharField(max_length=47, blank=True)

    user_data = models.TextField(
        blank=True, validators=[validate_yaml],
        help_text='Additional data that will be added to instance on provisioning')

    class Meta(object):
        abstract = True


class PrivateCloudMixin(models.Model):

    class Meta(object):
        abstract = True


class VirtualMachineMixin(BaseVirtualMachineMixin, CoordinatesMixin):
    def __init__(self, *args, **kwargs):
        AbstractFieldTracker().finalize_class(self.__class__, 'tracker')
        super(VirtualMachineMixin, self).__init__(*args, **kwargs)

    cores = models.PositiveSmallIntegerField(default=0, help_text='Number of cores in a VM')
    ram = models.PositiveIntegerField(default=0, help_text='Memory size in MiB')
    disk = models.PositiveIntegerField(default=0, help_text='Disk size in MiB')
    min_ram = models.PositiveIntegerField(default=0, help_text='Minimum memory size in MiB')
    min_disk = models.PositiveIntegerField(default=0, help_text='Minimum disk size in MiB')

    external_ips = models.GenericIPAddressField(null=True, blank=True, protocol='IPv4')
    internal_ips = models.GenericIPAddressField(null=True, blank=True, protocol='IPv4')

    image_name = models.CharField(max_length=150, blank=True)

    class Meta(object):
        abstract = True

    def detect_coordinates(self):
        if self.external_ips:
            return get_coordinates_by_ip(self.external_ips)

    def get_access_url(self):
        if self.external_ips:
            return self.external_ips
        if self.internal_ips:
            return self.internal_ips
        return None


class PublishableMixin(models.Model):
    """ Provide publishing_state field """

    class Meta(object):
        abstract = True

    class PublishingState(object):
        NOT_PUBLISHED = 'not published'
        PUBLISHED = 'published'
        REQUESTED = 'requested'

        CHOICES = ((NOT_PUBLISHED, _('Not published')), (PUBLISHED, _('Published')), (REQUESTED, _('Requested')))

    publishing_state = models.CharField(
        max_length=30, choices=PublishingState.CHOICES, default=PublishingState.NOT_PUBLISHED)


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


# XXX: This class should be deleted after NC-1237 implementation
class OldStateResourceMixin(core_models.ErrorMessageMixin, models.Model):
    """ Provides old-style states for resources """

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

    state = FSMIntegerField(
        default=States.PROVISIONING_SCHEDULED,
        choices=States.CHOICES,
        help_text="WARNING! Should not be changed manually unless you really know what you are doing.")

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
                source=[States.OFFLINE, States.ERRED],
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


@python_2_unicode_compatible
class ResourceMixin(MonitoringModelMixin,
                    core_models.UuidMixin,
                    core_models.DescribableMixin,
                    core_models.NameMixin,
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

    class Permissions(object):
        customer_path = 'service_project_link__project__customer'
        project_path = 'service_project_link__project'
        project_group_path = 'service_project_link__project__project_groups'
        service_path = 'service_project_link__service'

    service_project_link = NotImplemented
    backend_id = models.CharField(max_length=255, blank=True)
    tags = TaggableManager(related_name='+', blank=True)

    start_time = models.DateTimeField(blank=True, null=True)

    def get_backend(self, **kwargs):
        return self.service_project_link.get_backend(**kwargs)

    def get_cost(self, start_date, end_date):
        raise NotImplementedError(
            "Please refer to nodeconductor.billing.tasks.debit_customers while implementing it")

    def get_access_url(self):
        # default behaviour. Override in subclasses if applicable
        return None

    def get_access_url_name(self):
        return None

    @classmethod
    @lru_cache(maxsize=1)
    def get_all_models(cls):
        return [model for model in apps.get_models() if issubclass(model, cls)]

    @classmethod
    @lru_cache(maxsize=1)
    def get_vm_models(cls):
        # TODO: remove once iaas has been deprecated
        from nodeconductor.iaas.models import Instance
        return [resource for resource in cls.get_all_models()
                if issubclass(resource, VirtualMachineMixin) or issubclass(resource, Instance)]

    @classmethod
    @lru_cache(maxsize=1)
    def get_app_models(cls):
        # TODO: remove once iaas has been deprecated
        from nodeconductor.iaas.models import Instance
        return [resource for resource in cls.get_all_models()
                if not issubclass(resource, VirtualMachineMixin) and
                not issubclass(resource, Instance) and
                not issubclass(resource, PrivateCloudMixin)]

    @classmethod
    @lru_cache(maxsize=1)
    def get_private_cloud_models(cls):
        return [resource for resource in cls.get_all_models() if issubclass(resource, PrivateCloudMixin)]

    def get_related_resources(self):
        return itertools.chain(
            self._get_generic_related_resources(),
            self._get_concrete_related_resources(),
            self._get_concrete_linked_resources(),
            self._get_generic_linked_resources()
        )

    def _get_generic_related_resources(self):
        # For example, returns Zabbix host for virtual machine

        return itertools.chain.from_iterable(
            model.objects.filter(**{field.name: self})
            for model in ResourceMixin.get_all_models()
            for field in model._meta.virtual_fields
            if isinstance(field, GenericForeignKey))

    def _get_concrete_related_resources(self):
        # For example, returns GitLab projects for group

        return itertools.chain.from_iterable(
            rel.related_model.objects.filter(**{rel.field.name: self})
            for rel in self._meta.get_all_related_objects()
            if issubclass(rel.related_model, ResourceMixin)
        )

    def _get_concrete_linked_resources(self):
        # For example, returns GitLab group for project
        return [getattr(self, field.name)
                for field in self._meta.fields
                if isinstance(field, models.ForeignKey) and
                issubclass(field.related_model, ResourceMixin)]

    def _get_generic_linked_resources(self):
        # For example, returns GitLab group for project
        return [getattr(self, field.name)
                for field in self._meta.virtual_fields
                if isinstance(field, GenericForeignKey)]

    @classmethod
    @lru_cache(maxsize=1)
    def get_url_name(cls):
        """ This name will be used by generic relationships to membership model for URL creation """
        return '{}-{}'.format(cls._meta.app_label, cls.__name__.lower())

    def get_log_fields(self):
        return ('uuid', 'name', 'service_project_link', 'full_name')

    @property
    def full_name(self):
        return '%s %s' % (SupportedServices.get_name_for_model(self).replace('.', ' '), self.name)

    def _get_log_context(self, entity_name):
        context = super(ResourceMixin, self)._get_log_context(entity_name)
        # XXX: Add resource_full_name here, because event context does not support properties as fields
        context['resource_full_name'] = self.full_name
        # required for lookups in ElasticSearch by the client
        context['resource_type'] = SupportedServices.get_name_for_model(self)
        return context

    def filter_by_logged_object(self):
        return {
            'resource_uuid': self.uuid.hex,
            'resource_type': SupportedServices.get_name_for_model(self)
        }

    def get_parents(self):
        return [self.service_project_link]

    def __str__(self):
        return self.name


# deprecated, use NewResource instead.
class Resource(OldStateResourceMixin, ResourceMixin):

    class Meta(object):
        abstract = True


class NewResource(ResourceMixin, core_models.StateMixin):

    class Meta(object):
        abstract = True


class PublishableResource(PublishableMixin, Resource):

    class Meta(object):
        abstract = True
