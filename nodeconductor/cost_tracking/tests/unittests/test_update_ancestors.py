from django.test import TransactionTestCase

from nodeconductor.cost_tracking.tests import factories
from nodeconductor.cost_tracking.models import PriceEstimate
from nodeconductor.structure.tests import factories as structure_factories


class UpdateAncestorEstimateTest(TransactionTestCase):
    def setUp(self):
        super(UpdateAncestorEstimateTest, self).setUp()
        self.customer = structure_factories.CustomerFactory()
        self.project = structure_factories.ProjectFactory(customer=self.customer)
        self.settings = structure_factories.ServiceSettingsFactory(customer=self.customer)
        self.service = structure_factories.TestServiceFactory(customer=self.customer, settings=self.settings)
        self.link = structure_factories.TestServiceProjectLinkFactory(project=self.project, service=self.service)
        self.instance = structure_factories.TestInstanceFactory(service_project_link=self.link)
        self.instance_estimate = factories.PriceEstimateFactory(scope=self.instance)

    def test_resource_ancestor_estimates_are_service_customer_and_project(self):
        self.instance_estimate.update_ancestors()
        total = self.instance_estimate.total
        self.assertEqual(PriceEstimate.objects.get(scope=self.link).total, total)
        self.assertEqual(PriceEstimate.objects.get(scope=self.settings).total, total)
        self.assertEqual(PriceEstimate.objects.get(scope=self.service).total, total)
        self.assertEqual(PriceEstimate.objects.get(scope=self.customer).total, total)
        self.assertEqual(PriceEstimate.objects.get(scope=self.project).total, total)
