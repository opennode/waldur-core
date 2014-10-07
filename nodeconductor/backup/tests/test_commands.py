from django.test import TestCase

from mock import patch

from nodeconductor.backup.tests import factories
from nodeconductor.backup import models
from nodeconductor.backup.management.commands.executebackups import Command


class ExecuteBackupsTest(TestCase):

    def setUp(self):
        self.command = Command()

    def test_verify_executing_backups(self):
        states = models.Backup.States
        backuping_backup = factories.BackupFactory(state=states.BACKUPING, result_id='bid')
        restoring_backup = factories.BackupFactory(state=states.RESTORING, result_id='rid')
        deleting_backup = factories.BackupFactory(state=states.DELETING, result_id='did')

        with patch('nodeconductor.backup.tasks.backup_task.AsyncResult') as patched:
            self.command._verify_executing_backups()
            patched.assert_called_with(backuping_backup.result_id)
        with patch('nodeconductor.backup.tasks.restore_task.AsyncResult') as patched:
            self.command._verify_executing_backups()
            patched.assert_called_with(restoring_backup.result_id)
        with patch('nodeconductor.backup.tasks.delete_task.AsyncResult') as patched:
            self.command._verify_executing_backups()
            patched.assert_called_with(deleting_backup.result_id)
