import unittest
from rest_framework import test, status

from nodeconductor.core.utils import datetime_to_timestamp, timeshift
from nodeconductor.structure.models import CustomerRole, ProjectGroupRole
from nodeconductor.structure.tests.factories import CustomerFactory, UserFactory, ProjectFactory
from nodeconductor.logging.models import Alert
from nodeconductor.logging.tests.factories import AlertFactory
from nodeconductor.iaas.tests.factories import InstanceFactory
from nodeconductor.logging.serializers import StatsQuerySerializer

class TimeframeAlertsStatsTest(test.APITransactionTestCase):

    def setUp(self):
        self.staff = UserFactory(is_staff=True)

    def test_staff_receives_all_stats_within_timeframe(self):
        minutes = timeshift(minutes=-5)
        weeks = timeshift(weeks=-1)

        error_alert = AlertFactory(created=minutes, severity=Alert.SeverityChoices.ERROR)
        debug_alert = AlertFactory(created=minutes, severity=Alert.SeverityChoices.DEBUG)
        info_alert = AlertFactory(created=weeks, severity=Alert.SeverityChoices.INFO)

        self.client.force_authenticate(self.staff)
        response = self.client.get(AlertFactory.get_stats_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expected = {
            "Debug": 1,
            "Error": 1,
            "Info": 0,
            "Warning": 0
        }
        self.assertEqual(expected, dict(response.data))


class StructureAlertsStatsTest(test.APITransactionTestCase):
    def setUp(self):
        self.date = timeshift(minutes=-5)
        self.staff = UserFactory(is_staff=True)

        self.owner = UserFactory()
        self.customer = CustomerFactory()
        self.customer.add_user(self.owner, CustomerRole.OWNER)

        self.project1 = ProjectFactory(customer=self.customer)
        self.instance1 = InstanceFactory(cloud_project_membership__project=self.project1)

        self.project2 = ProjectFactory()
        self.instance2 = InstanceFactory(cloud_project_membership__project=self.project2)

        alert1 = AlertFactory(created=self.date,
            scope=self.instance1, severity=Alert.SeverityChoices.ERROR)

        alert2 = AlertFactory(created=self.date,
            scope=self.instance2, severity=Alert.SeverityChoices.INFO)

        self.project1_stats = {
            "Debug": 0,
            "Error": 1,
            "Info": 0,
            "Warning": 0
        }

        self.project2_stats = {
            "Debug": 0,
            "Error": 0,
            "Info": 1,
            "Warning": 0
        }

    def test_project_can_be_filtered_by_uuid(self):
        self.client.force_authenticate(self.staff)

        response = self.client.get(AlertFactory.get_stats_url(),
            data={'aggregate': 'project', 'uuid': self.project1.uuid.hex})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.project1_stats, dict(response.data))

        response = self.client.get(AlertFactory.get_stats_url(),
            data={'aggregate': 'project', 'uuid': self.project2.uuid.hex})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.project2_stats, dict(response.data))

    def test_owner_receive_data_for_his_project(self):
        self.client.force_authenticate(self.owner)
        response = self.client.get(AlertFactory.get_stats_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.project1_stats, dict(response.data))

class SerializerValidationTest(unittest.TestCase):
    def test_valid_data(self):
        serializer = StatsQuerySerializer(data={
            'start_time': '0',
            'aggregate': 'project',
            'uuid': '6a806164e4ac4541ae07fad62800ddb9'
        })
        self.assertTrue(serializer.is_valid())

    def test_invalid_data(self):
        serializer = StatsQuerySerializer(data={
            'model': 'INVALID_MODEL'
        })
        self.assertFalse(serializer.is_valid())

        serializer = StatsQuerySerializer(data={
            'start_time': '9999999999'
        })
        self.assertFalse(serializer.is_valid())
