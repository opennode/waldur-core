from django.test import TestCase
from mock import patch

from nodeconductor.core import utils
from nodeconductor.structure import tasks
from nodeconductor.structure.tests import factories


class TestDetectVMCoordinatesTask(TestCase):

    @patch('requests.get')
    def test_task_sets_coordinates(self, mock_request_get):
        ip_address = "127.0.0.1"
        expected_latitude = 20
        expected_longitude = 20
        instance = factories.TestInstanceFactory(external_ips=ip_address)

        mock_request_get.return_value.ok = True
        response = {"ip": ip_address, "latitude": expected_latitude, "longitude": expected_longitude}
        mock_request_get.return_value.json.return_value = response
        tasks.detect_vm_coordinates(utils.serialize_instance(instance))

        instance.refresh_from_db()
        self.assertEqual(instance.latitude, expected_latitude)
        self.assertEqual(instance.longitude, expected_longitude)

    @patch('requests.get')
    def test_task_does_not_set_coordinates_if_response_is_not_ok(self, mock_request_get):
        ip_address = "127.0.0.1"
        instance = factories.TestInstanceFactory(external_ips=ip_address)

        mock_request_get.return_value.ok = False
        tasks.detect_vm_coordinates(utils.serialize_instance(instance))

        instance.refresh_from_db()
        self.assertIsNone(instance.latitude)
        self.assertIsNone(instance.longitude)
