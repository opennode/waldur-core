import unittest
import celery
import mock

from celery.backends.base import Backend
from celery.app.task import Context

from django.test import testcases


@unittest.skip('')
class ExecutorTest(testcases.TestCase):
    @mock.patch('waldur_core.core.tasks.group')
    def test_use_old_signature_in_task_error(self, mock_group):
        app = celery.Celery()
        self.backend = Backend(app)
        errback = {"chord_size": None,
                   "task": "waldur_core.core.tasks.ErrorStateTransitionTask",
                   "args": ["waldur_jira.project:79"],
                   "immutable": False,
                   "subtask_type": None,
                   "kwargs": {},
                   "options": {}
                   }
        self.request = Context(errbacks=[errback], id='task_id', root_id='root_id')
        self.backend._call_task_errbacks(self.request, Exception('test'), '')
        self.assertEqual(mock_group.call_count, 1)
