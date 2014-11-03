from __future__ import unicode_literals

from django.contrib.auth.models import Group
from django.db import models
from django.db import transaction
from django.db.models import signals
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _

from nodeconductor.core.models import UuidMixin, DescribableMixin


@python_2_unicode_compatible
class Customer(UuidMixin, models.Model):
    class Permissions(object):
        customer_path = 'self'
        project_path = 'projects'

    name = models.CharField(max_length=160)
    abbreviation = models.CharField(max_length=8)
    contact_details = models.TextField()
    # XXX: How do we tell customers with same names from each other?

    def add_user(self, user, role_type):
        role = self.roles.get(role_type=role_type)
        role.permission_group.user_set.add(user)

    def remove_user(self, user, role_type=None):
        groups = user.groups.filter(role__customer=self)

        if role_type is not None:
            groups = groups.filter(role__role_type=role_type)

        with transaction.atomic():
            for group in groups.iterator():
                group.user_set.remove(user)

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


def create_customer_roles(sender, instance, created, **kwargs):
    if created:
        with transaction.atomic():
            owner_group = Group.objects.create(name='Role: {0} owner'.format(instance.uuid))

            instance.roles.create(role_type=CustomerRole.OWNER, permission_group=owner_group)

signals.post_save.connect(create_customer_roles,
                          sender=Customer,
                          weak=False,
                          dispatch_uid='structure.customer_roles_bootstrap')


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
    """ Project or user memory and CPU quotas """

    vcpu = models.PositiveIntegerField(help_text=_('Available CPUs'))
    ram = models.FloatField(help_text=_('Maximum available RAM size in GB'))
    storage = models.FloatField(help_text=_('Maximum available storage size in GB (incl. backup)'))
    max_instances = models.PositiveIntegerField(help_text=_('Maximum number of running instances'))


@python_2_unicode_compatible
class Project(DescribableMixin, UuidMixin, models.Model):
    class Permissions(object):
        customer_path = 'customer'
        project_path = 'self'

    name = models.CharField(max_length=80)
    customer = models.ForeignKey(Customer, related_name='projects')
    resource_quota = models.OneToOneField(ResourceQuota, related_name='project', null=True)

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

    def __str__(self):
        return '%(name)s | %(customer)s' % {
            'name': self.name,
            'customer': self.customer.name
        }


def create_project_roles(sender, instance, created, **kwargs):
    if created:
        with transaction.atomic():
            admin_group = Group.objects.create(name='Role: {0} admin'.format(instance.uuid))
            mgr_group = Group.objects.create(name='Role: {0} mgr'.format(instance.uuid))

            instance.roles.create(role_type=ProjectRole.ADMINISTRATOR, permission_group=admin_group)
            instance.roles.create(role_type=ProjectRole.MANAGER, permission_group=mgr_group)

signals.post_save.connect(create_project_roles,
                          sender=Project,
                          weak=False,
                          dispatch_uid='structure.project_roles_bootstrap')


@python_2_unicode_compatible
class ProjectGroupRole(UuidMixin, models.Model):
    class Meta(object):
        unique_together = ('project_group', 'role_type')

    MANAGER = 0

    TYPE_CHOICES = (
        (MANAGER, _('Group Manager')),
    )

    project_group = models.ForeignKey('structure.ProjectGroup', related_name='roles')
    role_type = models.SmallIntegerField(choices=TYPE_CHOICES)
    permission_group = models.OneToOneField(Group)

    def __str__(self):
        return self.get_role_type_display()

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


@python_2_unicode_compatible
class ProjectGroup(DescribableMixin, UuidMixin, models.Model):
    """
    Project groups are means to organize customer's projects into arbitrary sets.
    """
    class Permissions(object):
        customer_path = 'customer'
        project_path = 'projects'

    name = models.CharField(max_length=80)
    customer = models.ForeignKey(Customer, related_name='project_groups')
    projects = models.ManyToManyField(Project,
                                      related_name='project_groups')

    def __str__(self):
        return self.name


class NetworkSegment(models.Model):
    class Meta(object):
        unique_together = ('vlan', 'project')

    ip = models.GenericIPAddressField(primary_key=True)
    netmask = models.PositiveIntegerField(null=False)
    vlan = models.PositiveIntegerField(null=False)
    project = models.ForeignKey(Project, related_name='segments')
