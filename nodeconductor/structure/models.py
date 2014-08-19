from __future__ import unicode_literals

from django.contrib.auth.models import Group
from django.db import models
from django.db import transaction
from django.db.models import signals
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _
from guardian.shortcuts import assign_perm

from nodeconductor.core.models import UuidMixin
from nodeconductor.core.permissions import register_group_access


@python_2_unicode_compatible
class Customer(UuidMixin, models.Model):
    class Meta(object):
        permissions = (
            ('view_customer', _('Can see available customers')),
        )

    name = models.CharField(max_length=80)
    abbreviation = models.CharField(max_length=80)
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

    customer = models.ForeignKey(Customer, related_name='roles')
    role_type = models.SmallIntegerField(choices=TYPE_CHOICES)
    permission_group = models.OneToOneField(Group)

    def __str__(self):
        return self.get_role_type_display()


def create_customer_roles(sender, instance, created, **kwargs):
    if created:
        with transaction.atomic():
            owner_group = Group.objects.create(name='Role: {0} owner'.format(instance.pk))

            instance.roles.create(role_type=CustomerRole.OWNER, permission_group=owner_group)

            assign_perm('view_customer', owner_group, obj=instance)

signals.post_save.connect(create_customer_roles,
                          sender=Customer,
                          weak=False,
                          dispatch_uid='structure.customer_roles_bootstrap')


@python_2_unicode_compatible
class ProjectRole(models.Model):
    class Meta(object):
        unique_together = ('project', 'role_type')

    ADMINISTRATOR = 0
    MANAGER = 1

    TYPE_CHOICES = (
        (ADMINISTRATOR, _('Administrator')),
        (MANAGER, _('Manager')),
    )

    project = models.ForeignKey('structure.Project', related_name='roles')
    role_type = models.SmallIntegerField(choices=TYPE_CHOICES)
    permission_group = models.OneToOneField(Group)

    def __str__(self):
        return self.get_role_type_display()


@python_2_unicode_compatible
class Project(UuidMixin, models.Model):
    class Meta(object):
        permissions = (
            ('view_project', _('Can see available projects')),
        )

    name = models.CharField(max_length=80)
    customer = models.ForeignKey(Customer, related_name='projects')

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

            assign_perm('view_project', admin_group, obj=instance)
            assign_perm('view_project', mgr_group, obj=instance)

signals.post_save.connect(create_project_roles,
                          sender=Project,
                          weak=False,
                          dispatch_uid='structure.project_roles_bootstrap')


@python_2_unicode_compatible
class ProjectGroup(UuidMixin, models.Model):
    """
    Project groups are means to organize customer's projects into arbitrary sets.
    """
    class Meta(object):
        permissions = (
            ('view_projectgroup', _('Can see available project groups')),
        )

    name = models.CharField(max_length=80)
    customer = models.ForeignKey(Customer, related_name='project_groups')
    projects = models.ManyToManyField(Project, related_name='project_groups')

    def __str__(self):
        return self.name

register_group_access(
    ProjectGroup,
    (lambda instance: instance.customer.roles.get(
        role_type=CustomerRole.OWNER).permission_group),
    permissions=('view', 'change',),
    tag='owner',
)


class NetworkSegment(models.Model):
    class Meta(object):
        unique_together = ('vlan', 'project')

    ip = models.GenericIPAddressField(primary_key=True)
    netmask = models.PositiveIntegerField(null=False)
    vlan = models.PositiveIntegerField(null=False)
    project = models.ForeignKey(Project, related_name='segments')
