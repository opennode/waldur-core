import mock
from django.core import mail
from django import setup
from django.test import TestCase
from django.test.utils import override_settings

from nodeconductor.core.models import User
from nodeconductor.iaas.models import Instance
from nodeconductor.iaas.log import event_logger
from nodeconductor.iaas.tests import factories as iaas_factories
from nodeconductor.logging import models as logging_models
from nodeconductor.structure import models as structure_models
from nodeconductor.structure.tests import factories as structure_factories


class TestHook(TestCase):
    @override_settings(LOGGING={
        'version': 1,

        'handlers': {
            'hook': {
                'class': 'nodeconductor.logging.log.HookHandler'
            }
        },
        'loggers': {
            'nodeconductor': {
                'level': 'DEBUG',
                'handlers': ['hook']
            }
        }
    })
    def setUp(self):
        setup()
        self.owner = structure_factories.UserFactory()
        self.instance = iaas_factories.InstanceFactory()
        self.customer = self.instance.cloud_project_membership.project.customer
        self.customer.add_user(self.owner, structure_models.CustomerRole.OWNER)
        self.other_user = structure_factories.UserFactory()

        self.event_type = 'iaas_instance_creation_scheduled'
        self.other_event = 'iaas_instance_creation_succeeded'

    def test_email_hook_filters_events_by_user_and_event_type(self):
        # Create email hook for customer owner
        self.email_hook = logging_models.EmailHook.objects.create(user=self.owner,
            email=self.owner.email, event_types=[self.event_type])

        # Create email hook for another user
        self.other_hook = logging_models.EmailHook.objects.create(user=self.other_user,
            email=self.owner.email, event_types=[self.event_type])

        # This event is captured and email hook is triggered
        event_logger.instance.warning('Virtual machine creation has been scheduled.',
            event_type=self.event_type, event_context={'instance': self.instance})

        # This event is ignored because event_type doesn't match with hook
        event_logger.instance.warning('Virtual machine creation has succeded.',
            event_type=self.other_event, event_context={'instance': self.instance})

        # Test that one message has been sent for email hook of customer owner
        self.assertEqual(len(mail.outbox), 1)

        # Verify that destination address of message is correct
        self.assertEqual(mail.outbox[0].to, [self.email_hook.email])

    def test_webhook(self):
        # Create web hook for customer owner
        self.web_hook = logging_models.WebHook.objects.create(user=self.owner,
            destination_url='http://example.com/', event_types=[self.event_type])

        # Spy on requests
        with mock.patch('requests.post') as post:

            # Trigger event on instance of customer owner
            event_logger.instance.warning('Virtual machine creation has been scheduled.',
                event_type=self.event_type, event_context={'instance': self.instance})

            # Event is captured and POST request is triggered
            # because event_type and user_uuid match
            post.assert_called_once_with(self.web_hook.destination_url, json=mock.ANY, verify=False)
