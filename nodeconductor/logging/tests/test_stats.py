from rest_framework import test, status

from nodeconductor.logging.tests.factories import AlertFactory
from nodeconductor.structure import models as structure_models
from nodeconductor.structure.tests.factories import UserFactory
from nodeconductor.logging.models import Alert

class AlertsStatsTest(test.APITransactionTestCase):

    def setUp(self):
        self.staff = UserFactory(is_staff=True)

    def test_staff_counts_all_alerts(self):
        error_alert = AlertFactory(severity=Alert.SeverityChoices.ERROR)
        debug_alert = AlertFactory(severity=Alert.SeverityChoices.DEBUG)

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
