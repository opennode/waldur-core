# encoding: utf-8

from mock import patch
from django.test import TestCase

from nodeconductor.structure import tasks
from nodeconductor.structure.tests import models
from nodeconductor.core import utils as core_utils
from nodeconductor.structure.tests import factories


class TestTasks(TestCase):

    @patch('requests.get')
    def test_detect_vm_coordinates_sets_coordinates(self, mock_request_get):
        ip_address = "127.0.0.1"
        expected_latitude = 20
        expected_longitude = 20
        instance = factories.TestInstanceFactory(external_ips=ip_address)

        mock_request_get.return_value.ok = True
        response = {"ip": ip_address, "latitude": expected_latitude, "longitude": expected_longitude}
        mock_request_get.return_value.json.return_value = response
        tasks.detect_vm_coordinates(core_utils.serialize_instance(instance))

        instance_updated = models.TestInstance.objects.get(pk=instance.id)
        self.assertIsNotNone(instance_updated.latitude)
        self.assertEqual(instance_updated.latitude, expected_latitude)
        self.assertIsNotNone(instance_updated.longitude)
        self.assertEqual(instance_updated.longitude, expected_longitude)

    @patch('requests.get')
    def test_detect_vm_coordinates_does_not_set_coordinates_if_response_is_not_ok(self, mock_request_get):
        ip_address = "127.0.0.1"
        instance = factories.TestInstanceFactory(external_ips=ip_address)

        mock_request_get.return_value.ok = False
        tasks.detect_vm_coordinates(core_utils.serialize_instance(instance))

        instance_updated = models.TestInstance.objects.get(pk=instance.id)
        self.assertIsNone(instance_updated.latitude)
        self.assertIsNone(instance_updated.longitude)
