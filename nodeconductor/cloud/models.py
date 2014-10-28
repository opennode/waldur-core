from __future__ import unicode_literals

import logging
import re

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, URLValidator
from django.conf import settings
from django.db import models
from django.db.models import signals
from django.dispatch import receiver
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _
from django_fsm import FSMField, transition
from novaclient.v1_1 import client as nova_client
from novaclient.exceptions import Unauthorized
from keystoneclient.exceptions import CertificateConfigError, CMSError, ClientException
from keystoneclient.v2_0 import client as keystone_client
from uuidfield import UUIDField

from nodeconductor.core.models import DescribableMixin, SshPublicKey, UuidMixin
from nodeconductor.core.serializers import UnboundSerializerMethodField
from nodeconductor.core.signals import pre_serializer_fields
from nodeconductor.structure import models as structure_models
from nodeconductor.structure.filters import filter_queryset_for_user


logger = logging.getLogger(__name__)


def validate_known_keystone_urls(value):
    known_urls = settings.get('OPENSTACK_CREDENTIALS', {})
    if value not in known_urls:
        raise ValidationError('%s is not known OpenStack installation')


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

    name = models.CharField(max_length=100)
    customer = models.ForeignKey(structure_models.Customer, related_name='clouds')
    projects = models.ManyToManyField(
        structure_models.Project, related_name='clouds', through='CloudProjectMembership')

    # OpenStack backend specific fields
    username = models.CharField(max_length=100)
    password = models.CharField(max_length=100)

    auth_url = models.CharField(max_length=200, help_text='Keystone endpoint url',
                                validators=[URLValidator(), validate_known_keystone_urls])

    def __str__(self):
        return self.name

    def sync(self):
        """
        Synchronizes nodeconductor cloud with real cloud account
        """


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


# TODO: Create CloudProjectMembershipManager with link/unlink methods
# that handle key propagation
# TODO: Use these link/unlink methods in cloud project membership viewset
class CloudProjectMembershipManager(models.Manager):
    def link(self, cloud, project):
        """
        Link cloud to project and schedule synchronization to the backend.
        """
        membership = self.model(
            cloud=cloud,
            project=project,
        )

        # TODO: Schedule task uploading the public keys of project users
        # membership.add_ssh_public_key(...)

        return membership


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

    objects = CloudProjectMembershipManager()

    class Permissions(object):
        customer_path = 'cloud__customer'
        project_path = 'project'

    @transition(field=state, source=States.CREATING, target=States.READY)
    def _set_ready(self):
        pass

    @transition(field=state, source=States.CREATING, target=States.ERRED)
    def _set_erred(self):
        pass

    # TODO: Extract to backend
    def create_in_backend(self):
        """
        Create new tenant and store its uuid in tenant_uuid field
        """
        # XXX: this have to be moved to settings or implemented in other way
        # TODO: Lookup admin account in settings based on auth_url


        # Case 1: url, user, pass all filled, url is unknown
        # Try to get tenant list, 400 BAD REQUEST if failed

        ADMIN_TENANT = 'admin'
        try:
            keystone = keystone_client.Client(
                self.cloud.username, self.cloud.password, ADMIN_TENANT, auth_url=self.cloud.auth_url)

            tenant = keystone.tenants.create(
                tenant_name=self.project.name, description=self.project.description, enabled=True)
            self.tenant_uuid = tenant.id
            self._set_ready()
        # FIXME: Account for auth errors as well
        except (ClientException, CertificateConfigError, CMSError) as e:
            logger.exception('Failed to create CloudProjectMembership with id %s. %s', self.id, str(e))
            self._set_erred()
        self.save()

    def add_ssh_public_key(self, public_key):
        # Hereinafter comes backend specific code.
        # Eventually this should be extracted to OpenStack backend.

        # We want names to be more or less human readable in backend.
        # OpenStack only allows latin letters, digits, dashes, underscores and spaces
        # as key names, thus we mangle the original name.
        safe_name = re.sub(r'[^-a-zA-Z0-9 _]+', '_', public_key.name)
        key_name = '{0}-{1}'.format(public_key.uuid.hex, safe_name)
        key_fingerprint = public_key.fingerprint

        nova = nova_client.Client(
            self.cloud.username,
            self.cloud.password,
            self.tenant_uuid,
            self.cloud.auth_url,
        )

        try:
            # OpenStack ignores project boundaries when dealing with keys,
            # so the same key can be already there given it was propagated
            # via a different project
            logger.debug('Retrieving list of keys existing on backend')
            published_keys = set((k.name, k.fingerprint) for k in nova.keypairs.list())
            if (key_name, key_fingerprint) not in published_keys:
                logger.info('Propagating ssh public key %s (%s) to backend', key_fingerprint, key_name)
                nova.keypairs.create(name=key_name, public_key=public_key.public_key)
            else:
                logger.info('Not propagating ssh public key; key already exists on backend')
        except Unauthorized:
            logger.warning('Failed to propagate ssh public key; authorization failed', exc_info=1)


@receiver(signals.post_save, sender=SshPublicKey)
def propagate_new_key(sender, instance=None, created=False, **kwargs):
    if not created:
        return

    # TODO: Schedule propagation task(s)? instead of doing it inline
    # XXX: Come up with a solid strategy which projects are to be affected
    cloud_project_memberships = filter_queryset_for_user(CloudProjectMembership.objects.all(), instance.user)

    for membership in cloud_project_memberships.iterator():
        membership.add_ssh_public_key(instance)


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
