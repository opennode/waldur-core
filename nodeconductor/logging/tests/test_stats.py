from datetime import timedelta
from django.utils import timezone

from rest_framework import test, status

from nodeconductor.core.utils import datetime_to_timestamp
from nodeconductor.structure.models import CustomerRole, ProjectGroupRole
from nodeconductor.structure.tests.factories import CustomerFactory, UserFactory, ProjectFactory
from nodeconductor.logging.models import Alert
from nodeconductor.logging.tests.factories import AlertFactory
from nodeconductor.iaas.tests.factories import InstanceFactory


class TimeframeAlertsStatsTest(test.APITransactionTestCase):

    def setUp(self):
        self.staff = UserFactory(is_staff=True)

    def test_staff_counts_all_alerts_within_day(self):
        minutes = timezone.now() - timedelta(minutes=5)
        weeks = timezone.now() - timedelta(weeks=1)

        error_alert = AlertFactory(created=minutes,
            severity=Alert.SeverityChoices.ERROR)

        debug_alert = AlertFactory(created=minutes,
            severity=Alert.SeverityChoices.DEBUG)

        info_alert = AlertFactory(created=weeks,
            severity=Alert.SeverityChoices.DEBUG)

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
        self.date = timezone.now() - timedelta(minutes=5)
        self.staff = UserFactory(is_staff=True)

        self.project1 = ProjectFactory()
        self.instance1 = InstanceFactory(cloud_project_membership__project=self.project1)

        self.project2 = ProjectFactory()
        self.instance2 = InstanceFactory(cloud_project_membership__project=self.project2)

        alert1 = AlertFactory(created=self.date,
            scope=self.instance1, severity=Alert.SeverityChoices.ERROR)

        alert2 = AlertFactory(created=self.date,
            scope=self.instance2, severity=Alert.SeverityChoices.INFO)

    def test_alerts_filtered_by_project1(self):
        self.client.force_authenticate(self.staff)

        response = self.client.get(AlertFactory.get_stats_url(),
            data={'aggregate': 'project', 'uuid': self.project1.uuid.hex})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expected = {
            "Debug": 0,
            "Error": 1,
            "Info": 0,
            "Warning": 0
        }
        self.assertEqual(expected, dict(response.data))

    def test_alerts_filtered_by_project2(self):
        self.client.force_authenticate(self.staff)

        response = self.client.get(AlertFactory.get_stats_url(),
            data={'aggregate': 'project', 'uuid': self.project2.uuid.hex})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expected = {
            "Debug": 0,
            "Error": 0,
            "Info": 1,
            "Warning": 0
        }
        self.assertEqual(expected, dict(response.data))
