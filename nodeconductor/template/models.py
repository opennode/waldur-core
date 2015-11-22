from __future__ import unicode_literals

from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from polymorphic import PolymorphicModel

from nodeconductor.core import models as core_models
from nodeconductor.logging.log import LoggableMixin
from nodeconductor.template import get_template_services


@python_2_unicode_compatible
class Template(core_models.UuidMixin,
               core_models.UiDescribableMixin,
               LoggableMixin,
               models.Model):
    # Model doesn't inherit NameMixin, because name field must be unique.
    name = models.CharField(max_length=150, unique=True)
    is_active = models.BooleanField(default=False)

    def provision(self, options, **kwargs):
        for service in get_template_services():
            try:
                service_options = next(
                    o for o in options
                    if o.pop('service_type') == service.service_type)
            except StopIteration:
                continue
            else:
                service_instance = service.objects.get(base_template=self)
                service_instance.provision(service_options, **kwargs)

    def __str__(self):
        return self.name


@python_2_unicode_compatible
class TemplateService(PolymorphicModel, LoggableMixin, core_models.NameMixin):
    base_template = models.ForeignKey(Template, related_name='services')

    def provision(self, options, **kwargs):
        raise NotImplementedError(
            'Implement provision() that would perform provision of a service.')

    def __str__(self):
        return self.name

    class Meta(object):
        unique_together = ('base_template', 'name', 'polymorphic_ctype')
