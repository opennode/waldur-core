from __future__ import unicode_literals

import logging

from django.core.validators import MaxLengthValidator
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import models
from django.db import transaction
from django.utils.encoding import python_2_unicode_compatible
from model_utils.models import TimeStampedModel

from nodeconductor.core.log import EventLoggerAdapter
from nodeconductor.core.models import UuidMixin, DescribableMixin
from nodeconductor.quotas import models as quotas_models
from nodeconductor.structure.signals import structure_role_granted, structure_role_revoked


logger = logging.getLogger(__name__)
event_logger = EventLoggerAdapter(logger)


@python_2_unicode_compatible
class Customer(UuidMixin, TimeStampedModel):
    class Permissions(object):
        customer_path = 'self'
        project_path = 'projects'
        project_group_path = 'project_groups'

    name = models.CharField(max_length=160)
    native_name = models.CharField(max_length=160, default='', blank=True)
    abbreviation = models.CharField(max_length=8, blank=True)
    contact_details = models.TextField(blank=True, validators=[MaxLengthValidator(500)])

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
                role_name = role.get_role_type_display().lower()
                event_logger.info(
                    'User %s has gained role of %s in customer %s.',
                    user.username, role_name, self.name,
                    extra={
                        'customer': self,
                        'affected_user': user,
                        'event_type': 'role_granted',
                        'structure_type': 'customer',
                        'role_name': role_name,
                    },
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

                role_name = role.get_role_type_display().lower()
                event_logger.info(
                    'User %s has lost role of %s in customer %s.',
                    user.username, role_name, self.name,
                    extra={
                        'customer': self,
                        'affected_user': user,
                        'event_type': 'role_revoked',
                        'structure_type': 'customer',
                        'role_name': role_name,
                    },
                )

    def has_user(self, user, role_type=None):
        queryset = self.roles.filter(permission_group__user=user)

        if role_type is not None:
            queryset = queryset.filter(role_type=role_type)

        return queryset.exists()

    def get_owners(self):
        return self.roles.get(role_type=CustomerRole.OWNER).permission_group.user_set

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
class ProjectRole(UuidMixin, models.Model):
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
class Project(DescribableMixin, UuidMixin, quotas_models.QuotaModelMixin, TimeStampedModel):
    class Permissions(object):
        customer_path = 'customer'
        project_path = 'self'
        project_group_path = 'project_groups'

    QUOTAS_NAMES = ['vcpu', 'ram', 'storage', 'max_instances']

    name = models.CharField(max_length=80)
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
                role_name = role.get_role_type_display().lower()
                event_logger.info(
                    'User %s has gained role of %s in project %s.',
                    user.username, role_name, self.name,
                    extra={
                        'project': self,
                        'affected_user': user,
                        'event_type': 'role_granted',
                        'structure_type': 'project',
                        'role_name': role_name,
                    },
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

                role_name = role.get_role_type_display().lower()
                event_logger.info(
                    'User %s has lost role of %s in project %s.',
                    user.username, role_name, self.name,
                    extra={
                        'project': self,
                        'affected_user': user,
                        'event_type': 'role_revoked',
                        'structure_type': 'project',
                        'role_name': role_name,
                    },
                )

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
class ProjectGroupRole(UuidMixin, models.Model):
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
class ProjectGroup(DescribableMixin, UuidMixin, TimeStampedModel):
    """
    Project groups are means to organize customer's projects into arbitrary sets.
    """
    class Permissions(object):
        customer_path = 'customer'
        project_path = 'projects'
        project_group_path = 'self'

    name = models.CharField(max_length=80)
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
                role_name = role.get_role_type_display().lower()
                event_logger.info(
                    'User %s has gained role of %s in project group %s.',
                    user.username, role_name, self.name,
                    extra={
                        'project_group': self,
                        'affected_user': user,
                        'event_type': 'role_granted',
                        'structure_type': 'project_group',
                        'role_name': role_name,
                    },
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

                role_name = role.get_role_type_display().lower()
                event_logger.info(
                    'User %s has lost role of %s in project group %s.',
                    user.username, role_name, self.name,
                    extra={
                        'project_group': self,
                        'affected_user': user,
                        'event_type': 'role_revoked',
                        'structure_type': 'project_group',
                        'role_name': role_name,
                    },
                )

    def has_user(self, user, role_type=None):
        queryset = self.roles.filter(permission_group__user=user)

        if role_type is not None:
            queryset = queryset.filter(role_type=role_type)

        return queryset.exists()
