from __future__ import unicode_literals

from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from polymorphic import PolymorphicModel

from nodeconductor.core import models as core_models
from nodeconductor.core import fields as core_fields


@python_2_unicode_compatible
class Template(core_models.UuidMixin,
               core_models.UiDescribableMixin,
               models.Model):
    """ A template for provisioning IaaS instance and its services.
    """
    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=False)

    def __str__(self):
        return self.name


@python_2_unicode_compatible
class TemplateService(PolymorphicModel):
    name = models.CharField(max_length=100)
    template = models.ForeignKey(Template, related_name='services')

    def __str__(self):
        return self.name

    class Meta(object):
        unique_together = ('template', 'name')


class TemplateServiceIaaS(TemplateService):
    service = models.ForeignKey('iaas.Instance', related_name='+')
    flavor = models.ForeignKey('iaas.Flavor', blank=True, null=True, related_name='+')
    image = models.ForeignKey('iaas.Image', blank=True, null=True, related_name='+')
    sla = models.BooleanField(default=False)
    sla_level = models.DecimalField(max_digits=6, decimal_places=4, default=0, blank=True)
    backup_schedule = core_fields.CronScheduleBaseField(max_length=15, null=True, blank=True)

    class Meta:
        verbose_name = 'IaaS Service'
        verbose_name_plural = 'IaaS Services'
