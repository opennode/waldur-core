import os

from django.conf import settings
from django.core.management.base import BaseCommand
from optparse import make_option
from nodeconductor.core.docs import ApiDocs


class Command(BaseCommand):
    help = "Generate RST docs for DRF API"
    args = "[appname]"
    option_list = BaseCommand.option_list + (
        make_option('--store', '-s', action='store', dest='path',
                    default='docs/drfapi', help='Where to store docs.'),
    )

    def handle(self, *args, **options):
        path = options.get('path')
        path = path if path.startswith('/') else os.path.join(settings.BASE_DIR, path)

        if not os.path.isdir(path):
            os.makedirs(path)
        else:
            for f in os.listdir(path):
                if f.endswith(".rst"):
                    os.remove(os.path.join(path, f))

        self.stdout.write(self.style.MIGRATE_HEADING('Gather endpoints info'))
        docs = ApiDocs(apps=args)
        self.stdout.write(self.style.MIGRATE_HEADING('Write RST docs'))
        docs.generate(path)
