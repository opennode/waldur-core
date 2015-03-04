from __future__ import unicode_literals

from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from polymorphic import PolymorphicModel

from nodeconductor.core import models as core_models


@python_2_unicode_compatible
class Template(core_models.UuidMixin,
               core_models.UiDescribableMixin,
               models.Model):
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
