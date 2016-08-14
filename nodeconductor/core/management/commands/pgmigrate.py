from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db.models.signals import pre_save, pre_init, pre_delete, post_save, post_delete, post_init, post_syncdb
from optparse import make_option


class Command(BaseCommand):
    help = "Load data with disabled signals."
    option_list = BaseCommand.option_list + (
        make_option('--path', '-p', dest='path', default='nc.json', help='Path to dumped database.'),
    )

    def handle(self, *args, **options):
        path = options.get('path')
        for signal in [pre_save, pre_init, pre_delete, post_save, post_delete, post_init, post_syncdb]:
            signal.receivers = []
        call_command('loaddata', path)
