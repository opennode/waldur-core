from __future__ import unicode_literals

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import models
from django.db import transaction
from django.db.models import signals
from django.dispatch import receiver
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _

from nodeconductor.core.models import UuidMixin, DescribableMixin
from nodeconductor.structure.signals import structure_role_granted, structure_role_revoked


@python_2_unicode_compatible
class Customer(UuidMixin, models.Model):
    class Permissions(object):
        customer_path = 'self'
        project_path = 'projects'
        project_group_path = 'project_groups'

    name = models.CharField(max_length=160)
    abbreviation = models.CharField(max_length=8)
    contact_details = models.TextField()
    # XXX: How do we tell customers with same names from each other?

    def add_user(self, user, role_type):
        UserGroup = get_user_model().groups.through

        with transaction.atomic():
            role = self.roles.get(role_type=role_type)

            try:
                membership = UserGroup.objects.get(
                    user=user,
                    group__customerrole=role,
                )
                return membership, False
            except UserGroup.DoesNotExist:
                membership = UserGroup.objects.create(
                    user=user,
                    group=role.permission_group,
                )

                structure_role_granted.send(
                    sender=Customer,
                    structure=self,
                    user=user,
                    role=role_type,
                )
                return membership, True

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
                structure_role_revoked.send(
                    sender=Customer,
                    structure=self,
                    user=membership.user,
                    role=membership.group.customerrole.role_type,
                )

                membership.delete()

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
        (OWNER, _('Owner')),
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
        (ADMINISTRATOR, _('Administrator')),
        (MANAGER, _('Manager')),
    )

    ROLE_TO_NAME = {
        ADMINISTRATOR: 'admin',
        MANAGER: 'manager'
    }

    NAME_TO_ROLE = dict((v, k) for k, v in ROLE_TO_NAME.items())

    project = models.ForeignKey('structure.Project', related_name='roles')
    role_type = models.SmallIntegerField(choices=TYPE_CHOICES)
    permission_group = models.OneToOneField(Group)

    def __str__(self):
        return self.get_role_type_display()


class ResourceQuota(models.Model):
    """Project quotas"""
    vcpu = models.PositiveIntegerField(help_text=_('Virtual CPUs'))
    ram = models.FloatField(help_text=_('RAM size'))
    storage = models.FloatField(help_text=_('Storage size (incl. backup)'))
    max_instances = models.PositiveIntegerField(help_text=_('Number of running instances'))


@python_2_unicode_compatible
class Project(DescribableMixin, UuidMixin, models.Model):
    class Permissions(object):
        customer_path = 'customer'
        project_path = 'self'
        project_group_path = 'project_groups'

    name = models.CharField(max_length=80)
    customer = models.ForeignKey(Customer, related_name='projects')
    resource_quota = models.OneToOneField(ResourceQuota, related_name='project_quota', null=True)
    resource_quota_usage = models.OneToOneField(ResourceQuota, related_name='project_quota_usage', null=True)

    def add_user(self, user, role_type):
        UserGroup = get_user_model().groups.through

        with transaction.atomic():
            role = self.roles.get(role_type=role_type)

            try:
                membership = UserGroup.objects.get(
                    user=user,
                    group__projectrole=role,
                )
                return membership, False
            except UserGroup.DoesNotExist:
                membership = UserGroup.objects.create(
                    user=user,
                    group=role.permission_group,
                )

                structure_role_granted.send(
                    sender=Project,
                    structure=self,
                    user=user,
                    role=role_type,
                )
                return membership, True

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
                structure_role_revoked.send(
                    sender=Project,
                    structure=self,
                    user=membership.user,
                    role=membership.group.projectrole.role_type,
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


@python_2_unicode_compatible
class ProjectGroupRole(UuidMixin, models.Model):
    class Meta(object):
        unique_together = ('project_group', 'role_type')

    MANAGER = 0

    TYPE_CHOICES = (
        (MANAGER, _('Group Manager')),
    )

    ROLE_TO_NAME = {MANAGER: 'manager'}
    NAME_TO_ROLE = dict((v, k) for k, v in ROLE_TO_NAME.items())

    project_group = models.ForeignKey('structure.ProjectGroup', related_name='roles')
    role_type = models.SmallIntegerField(choices=TYPE_CHOICES)
    permission_group = models.OneToOneField(Group)

    def __str__(self):
        return self.get_role_type_display()


@python_2_unicode_compatible
class ProjectGroup(DescribableMixin, UuidMixin, models.Model):
    """
    Project groups are means to organize customer's projects into arbitrary sets.
    """
    class Permissions(object):
        customer_path = 'customer'
        project_path = 'projects'
        project_group_path = 'self'

    name = models.CharField(max_length=80)
    customer = models.ForeignKey(Customer, related_name='project_groups')
    projects = models.ManyToManyField(Project,
                                      related_name='project_groups')

    def __str__(self):
        return self.name

    def add_user(self, user, role_type):
        role = self.roles.get(role_type=role_type)
        role.permission_group.user_set.add(user)

    def remove_user(self, user, role_type=None):
        groups = user.groups.filter(role__project=self)

        if role_type is not None:
            groups = groups.filter(role__role_type=role_type)

        with transaction.atomic():
            for group in groups.iterator():
                group.user_set.remove(user)


class NetworkSegment(models.Model):
    class Meta(object):
        unique_together = ('vlan', 'project')

    ip = models.GenericIPAddressField(primary_key=True)
    netmask = models.PositiveIntegerField(null=False)
    vlan = models.PositiveIntegerField(null=False)
    project = models.ForeignKey(Project, related_name='segments')


# Signal handlers
@receiver(
    signals.post_save,
    sender=Project,
    dispatch_uid='nodeconductor.structure.models.create_project_roles',
)
def create_project_roles(sender, instance, created, **kwargs):
    if created:
        with transaction.atomic():
            admin_group = Group.objects.create(name='Role: {0} admin'.format(instance.uuid))
            mgr_group = Group.objects.create(name='Role: {0} mgr'.format(instance.uuid))

            instance.roles.create(role_type=ProjectRole.ADMINISTRATOR, permission_group=admin_group)
            instance.roles.create(role_type=ProjectRole.MANAGER, permission_group=mgr_group)


@receiver(
    signals.post_save,
    sender=Customer,
    dispatch_uid='nodeconductor.structure.models.create_customer_roles',
)
def create_customer_roles(sender, instance, created, **kwargs):
    if created:
        with transaction.atomic():
            owner_group = Group.objects.create(name='Role: {0} owner'.format(instance.uuid))

            instance.roles.create(role_type=CustomerRole.OWNER, permission_group=owner_group)


@receiver(
    signals.post_save,
    sender=ProjectGroup,
    dispatch_uid='nodeconductor.structure.models.create_project_group_roles',
)
def create_project_group_roles(sender, instance, created, **kwargs):
    if created:
        with transaction.atomic():
            mgr_group = Group.objects.create(name='Role: {0} group mgr'.format(instance.uuid))
            instance.roles.create(role_type=ProjectGroupRole.MANAGER, permission_group=mgr_group)
