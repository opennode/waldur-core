from __future__ import unicode_literals

from django.core.validators import URLValidator
from django.db import models
from django.db.models import signals
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _
from guardian.shortcuts import assign_perm, remove_perm

from nodeconductor.core.models import UuidMixin
from nodeconductor.structure import models as structure_models


@python_2_unicode_compatible
class Cloud(UuidMixin, models.Model):
    """
    A cloud instance information.

    Represents parameters set that are necessary to connect to a particular cloud,
    such as connection endpoints, credentials, etc.
    """
    class Meta(object):
        unique_together = (
            ('organization', 'name'),
        )

    name = models.CharField(max_length=100)
    organization = models.ForeignKey(structure_models.Organization)

    projects = models.ManyToManyField(structure_models.Project, related_name='clouds')

    def __str__(self):
        return self.name


@python_2_unicode_compatible
class Flavor(UuidMixin, models.Model):
    """
    A preset of computing resources.
    """

    class Meta(object):
        permissions = (
            ("view_flavor", _("Can see available flavors")),
        )

    name = models.CharField(max_length=100)
    cloud = models.ForeignKey(Cloud, related_name='flavors')

    cores = models.PositiveSmallIntegerField(help_text=_('Number of cores in a VM'))
    ram = models.FloatField(help_text=_('Memory size in GB'))
    disk = models.FloatField(help_text=_('Root disk size in GB'))

    def __str__(self):
        return self.name


def update_cloud_to_project_grants(instance, action, reverse, pk_set, **kwargs):
    # TODO: Optimize the number of SQL queries
    def marry_cloud_and_project(cloud, project):
        admins = project.roles.get(
            role_type=structure_models.Role.ADMINISTRATOR).permission_group
        managers = project.roles.get(
            role_type=structure_models.Role.MANAGER).permission_group

        # TODO: Grant access to cloud

        for flavor in cloud.flavors.iterator():
            assign_perm('view_flavor', admins, obj=flavor)
            assign_perm('view_flavor', managers, obj=flavor)

    def divorce_cloud_and_project(cloud, project):
        admins = project.roles.get(
            role_type=structure_models.Role.ADMINISTRATOR).permission_group
        managers = project.roles.get(
            role_type=structure_models.Role.MANAGER).permission_group

        # TODO: Revoke access from cloud

        for flavor in cloud.flavors.iterator():
            for permission in (
                    'view_flavor',
                    'change_flavor',
                    'delete_flavor',
                    'add_flavor',
            ):
                remove_perm(permission, admins, obj=flavor)
                remove_perm(permission, managers, obj=flavor)

    function_map = {
        'post_add': marry_cloud_and_project,
        'post_remove': divorce_cloud_and_project,
        'pre_clear': divorce_cloud_and_project,
    }
    relation_model_map = {
        False: (structure_models.Project, 'projects'),
        True: (Cloud, 'clouds'),
    }

    try:
        update_function = function_map[action]
    except KeyError:
        # We don't care about this kind of action
        return

    # Depending on "reverse", "instance" can be either cloud of project.
    # Bind it to the update_function
    if reverse:
        update_permissions = lambda cloud: update_function(cloud, instance)
    else:
        update_permissions = lambda project: update_function(instance, project)

    related_model, related_set_attribute = relation_model_map[reverse]

    if action == 'pre_clear':
        related_instances = getattr(instance, related_set_attribute).iterator()
    else:
        related_instances = related_model.objects.filter(pk__in=pk_set)

    for related_instance in related_instances:
        update_permissions(related_instance)


signals.m2m_changed.connect(update_cloud_to_project_grants,
                            sender=Cloud.projects.through,
                            weak=False,
                            dispatch_uid='project_level_level_permissions')


class OpenStackCloud(Cloud):
    class Meta(object):
        verbose_name = _('OpenStack Cloud')
        verbose_name_plural = _('OpenStack Clouds')

    username = models.CharField(max_length=100, blank=True)
    password = models.CharField(max_length=100, blank=True)

    unscoped_token = models.TextField(blank=True)
    scoped_token = models.TextField(blank=True)
    auth_url = models.CharField(max_length=200, validators=[URLValidator()])
