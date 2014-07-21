from __future__ import unicode_literals

from django.contrib.auth.models import Group
from django.db import models
from django.db import transaction
from django.db.models import signals
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _
from guardian.shortcuts import assign_perm

from nodeconductor.core.models import UuidMixin


@python_2_unicode_compatible
class Organization(models.Model):
    name = models.CharField(max_length=80)
    abbreviation = models.CharField(max_length=80)
    contact_details = models.TextField()

    def __str__(self):
        return '%(name)s (%(abbreviation)s)' % {
            'name': self.name,
            'abbreviation': self.abbreviation
        }


@python_2_unicode_compatible
class Role(models.Model):
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
    organization = models.ForeignKey(Organization, related_name='projects')

    def __str__(self):
        return _('Project \'%(name)s\' from %(organization)s') % {
            'name': self.name,
            'organization': self.organization.name
        }


def create_project_roles(sender, instance, created, **kwargs):
    if created:
        with transaction.atomic():
            admin_group = Group.objects.create(name='Role: {0} admin'.format(instance.uuid))
            mgr_group = Group.objects.create(name='Role: {0} mgr'.format(instance.uuid))

            instance.roles.create(role_type=Role.ADMINISTRATOR, permission_group=admin_group)
            instance.roles.create(role_type=Role.MANAGER, permission_group=mgr_group)

            assign_perm('view_project', admin_group, obj=instance)
            assign_perm('view_project', mgr_group, obj=instance)

signals.post_save.connect(create_project_roles,
                          sender=Project,
                          weak=False,
                          dispatch_uid='structure.project_roles_bootstrap')


@python_2_unicode_compatible
class Environment(models.Model):
    project = models.ForeignKey(Project, related_name='environments')
    
    DEVELOPMENT = 'd'
    TESTING = 't'
    STAGING = 's'
    PRODUCTION = 'p'

    ENVIRONMENT_CHOICES = {
        DEVELOPMENT: _('Development environment'),
        TESTING: _('Testing environment'),
        STAGING: _('Staging environment'),
        PRODUCTION: _('Production environment'),
    }

    kind = models.CharField(max_length=1, choices=ENVIRONMENT_CHOICES.iteritems())

    def __str__(self):
        return _('%(env)s of %(project)s') % {
            'env': self.ENVIRONMENT_CHOICES[self.kind],
            'project': self.project
        }


class NetworkSegment(models.Model):
    class Meta(object):
        unique_together = ('vlan', 'project')

    ip = models.GenericIPAddressField(primary_key=True)
    netmask = models.PositiveIntegerField(null=False)
    vlan = models.PositiveIntegerField(null=False)
    project = models.ForeignKey(Project, related_name='segments')
