# coding=utf-8
from __future__ import unicode_literals

from StringIO import StringIO

from django.core.management import call_command
from django.test import TestCase

from .. import factories


class DumpUsersCommandTest(TestCase):

    def test_dump_users_command_with_unicode_full_name(self):
        user = factories.UserFactory(full_name='äöur šipākøv')
        output = StringIO()
        try:
            call_command('dumpusers', stdout=output)
        except UnicodeDecodeError as e:
            self.fail(str(e))

        self.assertIn(user.full_name.encode('utf8'), output.getvalue())
