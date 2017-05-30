from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from rest_framework import test, status

from nodeconductor.cost_tracking.models import PriceEstimate
from nodeconductor.cost_tracking.tests.factories import PriceEstimateFactory
from nodeconductor.logging.models import Alert
from nodeconductor.logging.tasks import check_threshold
from nodeconductor.structure.tests.factories import ProjectFactory, UserFactory


# XXX: This tests should be moved to test_handlers. NC-1537.
class PriceEstimateThresholdAlertTest(test.APITestCase):
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
        self.client.force_authenticate(UserFactory(is_staff=True))

    def test_staff_can_set_and_update_threshold_for_project(self):
        project = ProjectFactory()

        # Price estimate is created implicitly
        self.set_project_threshold(project, 200)

        # Price estimate is updated
        self.set_project_threshold(project, 300)

    def set_project_threshold(self, project, threshold):
        project_url = ProjectFactory.get_url(project)

        url = PriceEstimateFactory.get_list_url('threshold')
        response = self.client.post(url, {
            'threshold': threshold,
            'scope': project_url
        })
        self.assertEqual(status.HTTP_200_OK, response.status_code, response.data)

        response = self.client.get(project_url)
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(threshold, response.data['price_estimate']['threshold'])
