from __future__ import unicode_literals

from django.core.management.base import BaseCommand, CommandError
from nodeconductor.iaas.models import Template, TemplateMapping

from nodeconductor.structure import models as structure_models
from nodeconductor.cloud import models


class Command(BaseCommand):
    args = '<template image_uuid>'
    help = """Create a template and map to an image UUID.

Arguments:
  template             template to create
  image_uuid           image UUID to use for setting up template mapping"""

    def handle(self, *args, **options):
        if len(args) < 2:
            self.stdout.write('Missing arguments.')
            return

        template_name = args[0]
        image_uuid = args[1]
        self.stdout.write('Creating a template %s and setting up a map to image %s...' % (template_name, image_uuid))
        template, created = Template.objects.get_or_create(name=template_name)
        if created:
            template.os = template_name
            template.is_active = True
            template.monthly_fee = 20
            template.setup_fee = 10
            template.sla_level = 95
            template.description = 'Sample template of %s linked to an image %s' % (template_name, image_uuid)
            template.save()

        mapping, created = TemplateMapping.objects.get_or_create(template=template, backend_image_id=image_uuid)
        print mapping