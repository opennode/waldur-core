from __future__ import unicode_literals
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    args = '<username password>'
    help = """Create a user with a specified username and password. User will be created as staff.

Arguments:
  username       username of the newly created user
  password       password of the newly created user"""

    def __init__(self, *args, **kwargs):
        # Options are defined in an __init__ method to support swapping out
        # custom user models in tests.
        super(Command, self).__init__(*args, **kwargs)
        self.UserModel = get_user_model()

    def handle(self, *args, **options):
        if len(args) < 2:
            raise CommandError('Missing arguments.')
            return

        self.stdout.write('NB! This is administrative command. '
                          'Passing password in plaintext on command line is not safe!')
        username = args[0]
        password = args[1]
        try:
            self.UserModel.objects.get(username=username)
        except self.UserModel.DoesNotExist:
            pass
        else:
            self.stderr.write("Error: username is already taken.")
            return

        self.stdout.write('Creating a user %s...' % username)
        user = self.UserModel.objects.create(username=username, last_login=datetime.now())
        user.set_password(password)
        user.is_staff = True
        user.save()
