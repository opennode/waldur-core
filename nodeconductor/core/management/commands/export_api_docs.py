import json
import logging

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()


class Command(BaseCommand):
    help = "Exports Waldur API Documentation in JSON format"

    def add_arguments(self, parser):
        parser.add_argument(
            '-o', '--output',
            dest='output', default=None,
            help='Specifies file to which the output is written. The output will be printed to stdout by default.',
        )

    def handle(self, *args, **options):
        # Rise logging level to prevent redundant log messages
        logging.disable(logging.CRITICAL)

        client = APIClient(HTTP_HOST='localhost')
        user, _ = User.objects.get_or_create(username='waldur_docs_exporter', is_staff=True)
        client.force_authenticate(user=user)
        response = client.get('/docs/?format=openapi')
        user.delete()

        if response.status_code != status.HTTP_200_OK:
            raise CommandError('Failed to get response from the server')

        data = json.loads(response.content)
        if options['output'] is None:
            self.stdout.write(str(data))
        else:
            with open(options['output'], 'w') as output_file:
                json.dump(data, output_file)

        # return logging level back
        logging.disable(logging.NOTSET)
