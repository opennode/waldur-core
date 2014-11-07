from __future__ import unicode_literals

import logging

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, URLValidator
from django.db import models
from django.db.models import signals
from django.dispatch import receiver
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _

from nodeconductor.cloud.backend import CloudBackendError
from nodeconductor.core.models import (
    DescribableMixin, SshPublicKey, SynchronizableMixin, UuidMixin,
)
from nodeconductor.core.serializers import UnboundSerializerMethodField
from nodeconductor.core.signals import pre_serializer_fields
from nodeconductor.structure import models as structure_models
from nodeconductor.structure.filters import filter_queryset_for_user


logger = logging.getLogger(__name__)

# User = get_user_model()


def validate_known_keystone_urls(value):
    from nodeconductor.cloud.backend.openstack import OpenStackBackend

    backend = OpenStackBackend()
    try:
        backend.get_credentials(value)
    except CloudBackendError:
        raise ValidationError('%s is not a known OpenStack deployment.' % value)


@python_2_unicode_compatible
class Cloud(UuidMixin, SynchronizableMixin, models.Model):
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

    name = models.CharField(max_length=100)
    customer = models.ForeignKey(structure_models.Customer, related_name='clouds')
    projects = models.ManyToManyField(
        structure_models.Project, related_name='clouds', through='CloudProjectMembership')

    # OpenStack backend specific fields
    auth_url = models.CharField(max_length=200, help_text='Keystone endpoint url',
                                validators=[URLValidator(), validate_known_keystone_urls])

    def get_backend(self):
        # TODO: Support different clouds instead of hard-coding
        # Importing here to avoid circular imports hell
        from nodeconductor.cloud.backend.openstack import OpenStackBackend

        return OpenStackBackend()

    def __str__(self):
        return self.name

    def sync(self):
        """
        Synchronizes nodeconductor cloud with real cloud account
        """


@python_2_unicode_compatible
class CloudProjectMembership(SynchronizableMixin, models.Model):
    """
    This model represents many to many relationships between project and cloud
    """

    cloud = models.ForeignKey(Cloud)
    project = models.ForeignKey(structure_models.Project)

    # OpenStack backend specific fields
    username = models.CharField(max_length=100, blank=True)
    password = models.CharField(max_length=100, blank=True)

    tenant_id = models.CharField(max_length=64, blank=True)

    class Meta(object):
        unique_together = ('cloud', 'tenant_id')

    class Permissions(object):
        customer_path = 'cloud__customer'
        project_path = 'project'

    def __str__(self):
        return '{0} | {1}'.format(self.cloud.name, self.project.name)


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


@python_2_unicode_compatible
class SecurityGroup(UuidMixin, DescribableMixin, models.Model):
    """
    This class contains openstack security groups.
    """

    tcp = 'tcp'
    udp = 'udp'

    PROTOCOL_CHOICES = (
        (tcp, _('tcp')),
        (udp, _('udp')),
    )

    name = models.CharField(max_length=127)
    protocol = models.CharField(max_length=3, choices=PROTOCOL_CHOICES)
    from_port = models.IntegerField(validators=[MaxValueValidator(65535),
                                                MinValueValidator(1)])
    to_port = models.IntegerField(validators=[MaxValueValidator(65535),
                                              MinValueValidator(1)])
    ip_range = models.IPAddressField()
    netmask = models.PositiveIntegerField(null=False)

    def __str__(self):
        return self.name


# Signal handlers
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

    if sender not in (CustomerSerializer, ProjectSerializer):
        return

    fields['clouds'] = UnboundSerializerMethodField(get_related_clouds)


@receiver(signals.post_save, sender=SshPublicKey)
def propagate_new_users_key_to_his_projects_clouds(sender, instance=None, created=False, **kwargs):
    if not created:
        return

    public_key = instance

    membership_queryset = filter_queryset_for_user(
        CloudProjectMembership.objects.all(), public_key.user)

    membership_pks = membership_queryset.values_list('pk', flat=True)

    if membership_pks:
        # Note: importing here to avoid circular import hell
        from nodeconductor.cloud import tasks

        tasks.push_ssh_public_keys.delay([public_key.uuid], membership_pks)


# @receiver(signals.m2m_changed, sender=User.groups.through)
# @receiver(signals.m2m_changed)
def propagate_users_keys_to_his_projects_clouds(sender, instance, action, reverse, model, pk_set, **kwargs):
    # XXX: This is fragile
    if sender._meta.model_name != 'user_groups' or action != 'post_add':
        return

    if reverse:
        # instance is group
        # pk_set   is a set of user pks
        key_filter = {'user__pk__in': pk_set}
        membership_filter = {
            'project__roles__permission_group': instance,
        }
    else:
        # instance is user
        # pk_set   is a set of group pks
        key_filter = {'user': instance}
        membership_filter = {
            'project__roles__permission_group__pk__in': pk_set,
        }

    ssh_public_key_uuids = SshPublicKey.objects.filter(
        **key_filter).values_list('uuid', flat=True)

    membership_pks = CloudProjectMembership.objects.filter(
        **membership_filter).distinct().values_list('pk', flat=True)

    if ssh_public_key_uuids and membership_pks:
        # Note: importing here to avoid circular import hell
        from nodeconductor.cloud import tasks

        # Send uuids as strings rather than UUID objects
        tasks.push_ssh_public_keys.delay(
            [k.hex for k in ssh_public_key_uuids], membership_pks)


# @receiver(signals.post_save, sender=User.groups.through)
@receiver(signals.post_save)
def propagate_users_keys_to_his_projects_clouds2(sender, instance=None, created=False, **kwargs):
    # XXX: This is fragile
    if sender._meta.model_name != 'user_groups' or not created:
        return

    key_filter = {'user': instance.user}
    membership_filter = {
        'project__roles__permission_group': instance.group,
    }

    ssh_public_key_uuids = SshPublicKey.objects.filter(
        **key_filter).values_list('uuid', flat=True)

    membership_pks = CloudProjectMembership.objects.filter(
        **membership_filter).distinct().values_list('pk', flat=True)

    if ssh_public_key_uuids and membership_pks:
        # Note: importing here to avoid circular import hell
        from nodeconductor.cloud import tasks

        # Send uuids as strings rather than UUID objects
        tasks.push_ssh_public_keys.delay(
            [k.uuid for k in ssh_public_key_uuids], membership_pks)


# FIXME: These should come from backend properly, see NC-139
# Remove after NC-139 is implemented
@receiver(signals.post_save, sender=Cloud)
def create_dummy_flavors(sender, instance=None, created=False, **kwargs):
    if created:
        instance.flavors.create(
            name='Weak & Small',
            cores=2,
            ram=2 * 1024,
            disk=10 * 1024,
        )
        instance.flavors.create(
            name='Powerful & Small',
            cores=16,
            ram=2 * 1024,
            disk=10 * 1024,
        )
        instance.flavors.create(
            name='Weak & Large',
            cores=2,
            ram=32 * 1024,
            disk=100 * 1024,
        )
        instance.flavors.create(
            name='Powerful & Large',
            cores=16,
            ram=32 * 1024,
            disk=100 * 1024,
        )
