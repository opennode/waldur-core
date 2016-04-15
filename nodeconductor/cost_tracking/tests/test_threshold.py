from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from rest_framework import test, status

from nodeconductor.cost_tracking.models import PriceEstimate
from nodeconductor.cost_tracking.tests.factories import PriceEstimateFactory
from nodeconductor.logging.models import Alert
from nodeconductor.logging.tasks import check_threshold
from nodeconductor.structure.tests.factories import ProjectFactory, UserFactory


class PriceEstimateThresholdAlertTest(test.APITransactionTestCase):
    def test_price_estimate_is_copied_from_previous_one(self):
        project = ProjectFactory()
        estimate1 = PriceEstimateFactory(year=2015, month=12, scope=project, threshold=100)
        estimate2 = PriceEstimate.objects.create(year=2016, month=1, scope=project)
        self.assertEqual(estimate1.threshold, estimate2.threshold)

    def test_if_price_estimation_is_over_threshold_alert_is_created(self):
        self.assertTrue(self.is_alert_created(threshold=100, total=120))

    def test_if_price_estimation_is_under_threshold_alert_is_not_created(self):
        self.assertFalse(self.is_alert_created(threshold=100, total=90))

    def is_alert_created(self, threshold, total):
        project = ProjectFactory()
        dt = timezone.now()
        PriceEstimateFactory(year=dt.year, month=dt.month, scope=project, threshold=threshold, total=total)
        check_threshold()

        return Alert.objects.filter(
            content_type=ContentType.objects.get_for_model(project),
            object_id=project.id,
            alert_type='threshold_exceeded').exists()


class PriceEstimateThresholdApiTest(test.APITransactionTestCase):
    def setUp(self):
        self.estimate = PriceEstimateFactory(threshold=100)
        self.client.force_authenticate(UserFactory(is_staff=True))
        self.url = PriceEstimateFactory.get_url(self.estimate, 'threshold')

    def test_staff_can_update_threshold_of_price_estimate(self):
        response = self.client.post(self.url, {'threshold': 200})

        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.estimate.refresh_from_db()
        self.assertEqual(200, self.estimate.threshold)
