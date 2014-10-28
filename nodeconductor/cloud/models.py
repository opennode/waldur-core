from __future__ import unicode_literals
from django.core.exceptions import ValidationError

from django.core.validators import URLValidator, MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import signals
from django.dispatch import receiver
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _

from nodeconductor.core.models import UuidMixin, DescribableMixin
from nodeconductor.core.serializers import UnboundSerializerMethodField
from nodeconductor.core.signals import pre_serializer_fields
from nodeconductor.structure import models as structure_models
from nodeconductor.structure.filters import filter_queryset_for_user


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
    projects = models.ManyToManyField(structure_models.Project, related_name='clouds')

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
