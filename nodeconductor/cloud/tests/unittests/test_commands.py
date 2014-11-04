from django.test import TestCase
from django.core.management import call_command
from django.core.management.base import CommandError

from mock import patch

from nodeconductor.cloud.tests import factories
from nodeconductor.cloud import models
from nodeconductor.structure.tests import factories as structure_factories


class SyncCloudTest(TestCase):

    def test_sync_single_cloud(self):
        cloud1 = factories.CloudFactory()
        cloud2 = factories.CloudFactory()
        with patch('nodeconductor.cloud.models.Cloud.sync') as patched_method:
            call_command('synccloud', str(cloud1.uuid), str(cloud2.uuid))
            patched_method.assert_called_with()
            self.assertEqual(patched_method.call_count, 2)
        # error if wrong cloud uuid:
        self.assertRaises(CommandError, lambda: call_command('synccloud', "wrong_uuid"))

    def test_sync_customer_clouds(self):
        customer = structure_factories.CustomerFactory()
        [factories.CloudFactory(customer=customer) for i in range(5)]
        factories.CloudFactory()
        with patch('nodeconductor.cloud.models.Cloud.sync') as patched_method:
            call_command('synccloud', customer=str(customer.uuid), all=True)
            patched_method.assert_called_with()
            self.assertEqual(patched_method.call_count, customer.clouds.count())
        # error with wrong customer uuid:
        self.assertRaises(CommandError, lambda: call_command('synccloud', customer="wrong_uuid"))
        # error without all flag:
        self.assertRaises(CommandError, lambda: call_command('synccloud', customer=str(customer.uuid)))

    def test_sync_all_clouds(self):
        [factories.CloudFactory() for i in range(5)]
        with patch('nodeconductor.cloud.models.Cloud.sync') as patched_method:
            call_command('synccloud', all=True)
            patched_method.assert_called_with()
            self.assertEqual(patched_method.call_count, models.Cloud.objects.count())
