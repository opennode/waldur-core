import mock
from django.test import TestCase

from nodeconductor.logging import models as logging_models
from nodeconductor.logging.tests import factories as logging_factories
from nodeconductor.structure.filters import AggregateFilter
from nodeconductor.structure.tests import factories


class AggregateFilterTest(TestCase):

    def setUp(self):
        self.customer = factories.CustomerFactory()
        self.project = factories.ProjectFactory()
        self.sut = AggregateFilter()
        self.queryset = logging_models.Alert.objects

    def test_service_alert_is_included_when_customer_is_the_same(self):
        scope = factories.TestServiceFactory(customer=self.customer)
        alert = logging_factories.AlertFactory(scope=scope)

        result = self._make_aggregate_request('customer', self.customer.uuid.hex)

        self.assertEqual(len(result), 1)
        self.assertTrue(result.filter(uuid=alert.uuid).exists())

    def test_project_alert_is_not_included_when_it_belongs_to_another_customer(self):
        alert = logging_factories.AlertFactory(scope=factories.ProjectFactory())

        result = self._make_aggregate_request('customer', self.customer.uuid.hex)

        self.assertFalse(result.filter(uuid=alert.uuid).exists())

    def test_only_customer_related_scopes_are_returned(self):
        customer_related_alerts = []
        invalid_alert = logging_factories.AlertFactory(scope=factories.ProjectFactory())
        spl = factories.TestServiceProjectLinkFactory(service__customer=self.customer)
        customer_related_alerts.append(logging_factories.AlertFactory(scope=spl))
        service = factories.TestServiceFactory(customer=self.customer)
        customer_related_alerts.append(logging_factories.AlertFactory(scope=service))
        customer_related_alerts_ids = [a.uuid for a in customer_related_alerts]

        result = self._make_aggregate_request('customer', self.customer.uuid.hex)

        self.assertEqual(len(result), len(customer_related_alerts))
        self.assertEqual(result.filter(uuid__in=customer_related_alerts_ids).count(), len(customer_related_alerts_ids))
        self.assertFalse(result.filter(uuid=invalid_alert.uuid).exists())

    def test_service_project_link_alert_is_not_returned_when_it_is_related_to_another_project(self):
        not_owned_alert = logging_factories.AlertFactory(scope=factories.TestServiceProjectLinkFactory())
        spl = factories.TestServiceProjectLinkFactory(project=self.project)
        owned_alert = logging_factories.AlertFactory(scope=spl)

        result = self._make_aggregate_request('project', self.project.uuid.hex)

        self.assertTrue(result.filter(uuid=owned_alert.uuid).exists())
        self.assertFalse(result.filter(uuid=not_owned_alert.uuid).exists())

    def _make_aggregate_request(self, aggregate_by, uuid):
        request = mock.Mock()
        request.query_params = {
            'aggregate': aggregate_by,
            'uuid': uuid,
        }

        return self.sut.filter(request, self.queryset, None)




