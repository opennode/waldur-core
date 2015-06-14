from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from rest_framework import test, status

from nodeconductor.logging import models
from nodeconductor.logging.tests import factories
# Dependency from `structure` application exists only in tests
from nodeconductor.structure import models as structure_models
from nodeconductor.structure.tests import factories as structure_factories


class AlertsListTest(test.APITransactionTestCase):

    def setUp(self):
        self.customer = structure_factories.CustomerFactory()
        self.owner = structure_factories.UserFactory()
        self.customer.add_user(self.owner, structure_models.CustomerRole.OWNER)

    def test_customer_owner_can_see_alert_about_his_customer(self):
        alert = factories.AlertFactory(scope=self.customer)

        self.client.force_authenticate(self.owner)
        response = self.client.get(factories.AlertFactory.get_list_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(alert.uuid.hex, [a['uuid'] for a in response.data])

    def test_customer_owner_cannot_see_alert_about_other_customer(self):
        alert = factories.AlertFactory()

        self.client.force_authenticate(self.owner)
        response = self.client.get(factories.AlertFactory.get_list_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn(alert.uuid.hex, [a['uuid'] for a in response.data])


class AlertsCreateUpdateDeleteTest(test.APITransactionTestCase):

    def setUp(self):
        self.project = structure_factories.ProjectFactory()
        self.staff = get_user_model().objects.create_superuser(
            username='staff', password='staff', email='staff@example.com')
        self.alert = factories.AlertFactory.build(scope=self.project)
        severity_names = dict(models.Alert.SeverityChoices.CHOICES)
        self.valid_data = {
            'scope': structure_factories.ProjectFactory.get_url(self.project),
            'alert_type': self.alert.alert_type,
            'message': self.alert.message,
            'severity': severity_names[self.alert.severity],
        }
        self.url = factories.AlertFactory.get_list_url()

    def test_alert_can_be_created_by_staff(self):
        self.client.force_authenticate(self.staff)
        response = self.client.post(self.url, data=self.valid_data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        ct = ContentType.objects.get_for_model(structure_models.Project)
        self.assertTrue(models.Alert.objects.filter(
            content_type=ct, object_id=self.project.id, alert_type=self.alert.alert_type).exists())

    def test_alert_severity_can_be_updated(self):
        self.alert.save()
        self.valid_data['severity'] = 'Critical'

        self.client.force_authenticate(self.staff)
        response = self.client.post(self.url, data=self.valid_data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        ct = ContentType.objects.get_for_model(structure_models.Project)
        self.assertTrue(models.Alert.objects.filter(
            content_type=ct,
            object_id=self.project.id,
            alert_type=self.alert.alert_type,
            severity=models.Alert.SeverityChoices.CRITICAL).exists()
        )

    def test_alert_can_be_closed(self):
        self.alert.save()

        self.client.force_authenticate(self.staff)
        response = self.client.post(factories.AlertFactory.get_url(self.alert, 'close'))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        ct = ContentType.objects.get_for_model(structure_models.Project)
        self.assertTrue(models.Alert.objects.filter(
            content_type=ct,
            object_id=self.project.id,
            alert_type=self.alert.alert_type,
            closed__isnull=False).exists()
        )
