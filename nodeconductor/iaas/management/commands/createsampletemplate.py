from __future__ import unicode_literals
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError

from nodeconductor.iaas.models import Template, TemplateMapping


class Command(BaseCommand):
    # TODO: refactor after moving to Django 1.7 to use argparse
    args = '<template_name image_id>'
    help = """Create a template and map to a provided image reference.

Arguments:
  template_name       template name to update/create
  image_id            image UUID to use for setting up template mapping"""

    def handle(self, *args, **options):
        if len(args) < 2:
            raise CommandError('Missing arguments.')
            return

        template_name = args[0]
        image_id = args[1]
        self.stdout.write('Creating a template %s and setting up a mapping to image %s...'
                          % (template_name, image_id))
        template, _ = Template.objects.get_or_create(
            name=template_name,
            defaults={
                'os': template_name,
                'is_active': True,
                'monthly_fee': Decimal('20.0'),
                'setup_fee': Decimal('10.0'),
                'sla_level': Decimal('95.0'),
                'description': 'Sample template of %s linked to an image %s' % (template_name, image_id)
            },
        )

        mapping, _ = TemplateMapping.objects.get_or_create(template=template, backend_image_id=image_id)
        self.stdout.write('Mapping created: %s' % mapping)
