from __future__ import unicode_literals
from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import ugettext_lazy as _
from django.core.validators import URLValidator

from nodeconductor.structure import models as structure_models
from nodeconductor.core.models import UuidMixin


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

    def __str__(self):
        return self.name


@python_2_unicode_compatible
class Flavor(UuidMixin, models.Model):
    """
    A preset of computing resources.
    """
    name = models.CharField(max_length=100)
    cloud = models.ForeignKey(Cloud, related_name='flavors')

    cores = models.PositiveSmallIntegerField(help_text=_('Number of cores in a VM'))
    ram = models.FloatField(help_text=_('Memory size in GB'))
    disk = models.FloatField(help_text=_('Root disk size in GB'))

    def __str__(self):
        return self.name


class OpenStackCloud(Cloud):
    class Meta(object):
        verbose_name = _('OpenStack Cloud')
        verbose_name_plural = _('OpenStack Clouds')

    username = models.CharField(max_length=100, blank=True)
    password = models.CharField(max_length=100, blank=True)

    unscoped_token = models.TextField(blank=True)
    scoped_token = models.TextField(blank=True)
    auth_url = models.CharField(max_length=200, validators=[URLValidator()])
