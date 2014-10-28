from __future__ import unicode_literals

import logging

from django.core.validators import URLValidator
from django.db import models
from django.db.models import signals
from django.dispatch import receiver
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _
from django_fsm import FSMField, transition
from keystoneclient.v2_0 import client
from uuidfield import UUIDField

from nodeconductor.core.models import UuidMixin
from nodeconductor.core.serializers import UnboundSerializerMethodField
from nodeconductor.core.signals import pre_serializer_fields
from nodeconductor.structure import models as structure_models
from nodeconductor.structure.filters import filter_queryset_for_user


logger = logging.getLogger(__name__)


@python_2_unicode_compatible
class Cloud(UuidMixin, models.Model):
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

    username = models.CharField(max_length=100, blank=True)
    password = models.CharField(max_length=100, blank=True)

    name = models.CharField(max_length=100)
    customer = models.ForeignKey(structure_models.Customer, related_name='clouds')
    projects = models.ManyToManyField(
        structure_models.Project, related_name='clouds', through='CloudProjectMembership')

    unscoped_token = models.TextField(blank=True)
    scoped_token = models.TextField(blank=True)
    auth_url = models.CharField(max_length=200, validators=[URLValidator()])

    def __str__(self):
        return self.name

    def sync(self):
        """
        Synchronizes nodeconductor cloud with real cloud account
        """
        pass


def get_related_clouds(obj, request):
    related_clouds = obj.clouds.all()

    try:
        user = request.user
        related_clouds = filter_queryset_for_user(related_clouds, user)
    except AttributeError:
        pass

    from nodeconductor.cloud.serializers import BasicCloudSerializer
    serializer_instance = BasicCloudSerializer(related_clouds, context={'request': request})

    return serializer_instance.data


# These hacks are necessary for Django <1.7
# TODO: Refactor to use app.ready() after transition to Django 1.7
# See https://docs.djangoproject.com/en/1.7/topics/signals/#connecting-receiver-functions

# @receiver(pre_serializer_fields, sender=CustomerSerializer)
@receiver(pre_serializer_fields)
def add_clouds_to_related_model(sender, fields, **kwargs):
    # Note: importing here to avoid circular import hell
    from nodeconductor.structure.serializers import CustomerSerializer, ProjectSerializer

    if not sender in (CustomerSerializer, ProjectSerializer):
        return

    fields['clouds'] = UnboundSerializerMethodField(get_related_clouds)


class CloudProjectMembership(models.Model):
    """
    This model represents many to many relationships between project and cloud
    """
    class States(object):
        CREATING = 'c'
        READY = 'r'
        ERRED = 'e'

        CHOICES = (
            (CREATING, 'Creating'),
            (READY, 'Ready'),
            (ERRED, 'Erred'),
        )

    cloud = models.ForeignKey(Cloud)
    project = models.ForeignKey(structure_models.Project)
    tenant_uuid = UUIDField(unique=True, null=True)
    state = FSMField(default=States.CREATING, max_length=1, choices=States.CHOICES)

    class Permissions(object):
        customer_path = 'cloud__customer'
        project_path = 'project'

    @transition(field=state, source=States.CREATING, target=States.READY)
    def _set_ready(self):
        pass

    @transition(field=state, source=States.CREATING, target=States.ERRED)
    def _set_erred(self):
        pass

    def create_in_backend(self):
        """
        Create new tenant and store its uuid in tenant_uuid field
        """
        # XXX: this have to be moved to settings or implemented in other way
        ADMIN_TENANT = 'admin'
        try:
            keystone = client.Client(
                self.cloud.username, self.cloud.password, ADMIN_TENANT, auth_url=self.cloud.auth_url)
            tenant = keystone.tenants.create(
                tenant_name=self.project.name, description=self.project.description, enabled=True)
            self.tenant_uuid = tenant.id
            self._set_ready()
        except Exception as e:
            logger.exception('Failed to create CloudProjectMembership with id %s. %s', self.id, str(e))
            self._set_erred()
        self.save()


@python_2_unicode_compatible
class Flavor(UuidMixin, models.Model):
    """
    A preset of computing resources.
    """

    class Permissions(object):
        customer_path = 'cloud__projects__customer'
        project_path = 'cloud__projects'

    name = models.CharField(max_length=100)
    cloud = models.ForeignKey(Cloud, related_name='flavors')

    cores = models.PositiveSmallIntegerField(help_text=_('Number of cores in a VM'))
    ram = models.FloatField(help_text=_('Memory size in GB'))
    disk = models.FloatField(help_text=_('Root disk size in GB'))

    def __str__(self):
        return self.name


# These should come from backend properly
@receiver(signals.post_save, sender=Cloud)
def create_dummy_flavors(sender, instance=None, created=False, **kwargs):
    if created:
        instance.flavors.create(
            name='Weak & Small',
            cores=2,
            ram=2.0,
            disk=10.0,
        )
        instance.flavors.create(
            name='Powerful & Small',
            cores=16,
            ram=2.0,
            disk=10.0,
        )
        instance.flavors.create(
            name='Weak & Large',
            cores=2,
            ram=32.0,
            disk=100.0,
        )
        instance.flavors.create(
            name='Powerful & Large',
            cores=16,
            ram=32.0,
            disk=100.0,
        )


class SecurityGroups(object):
    """
    This class contains list of hard coded openstack security groups.
    """
    groups = [
        {
            "name": "test security group",
            "description": "test security group description",
            "protocol": "tcp",
            "from_port": 1,
            "to_port": 65535,
            "ip_range": "0.0.0.0/0"
        }
    ]

    groups_names = [g['name'] for g in groups]
