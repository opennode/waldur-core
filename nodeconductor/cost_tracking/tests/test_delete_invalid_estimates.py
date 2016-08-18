from django.test import TestCase

from nodeconductor.core.utils import silent_call
from nodeconductor.structure.tests import factories as structure_factories

from .. import models
from . import factories


class DeleteInvalidPriceEstimatesTest(TestCase):
    def setUp(self):
        customer = structure_factories.CustomerFactory()
        settings = structure_factories.ServiceSettingsFactory(customer=customer)
        service = structure_factories.TestServiceFactory(settings=settings, customer=customer)
        project = structure_factories.ProjectFactory(customer=customer)
        link = structure_factories.TestServiceProjectLinkFactory(service=service, project=project)
        self.resource = structure_factories.TestInstanceFactory(service_project_link=link)

        self.resource_estimate = factories.PriceEstimateFactory(scope=self.resource)
        year = self.resource_estimate.year
        month = self.resource_estimate.month

        self.customer_estimate = factories.PriceEstimateFactory(
            scope=customer, year=year, month=month
        )

        self.service_estimate = factories.PriceEstimateFactory(
            scope=service, year=year, month=month
        )

        self.settings_estimate = factories.PriceEstimateFactory(
            scope=settings, year=year, month=month
        )

        self.link_estimate = factories.PriceEstimateFactory(
            scope=link, year=year, month=month
        )

        self.project_estimate = factories.PriceEstimateFactory(
            scope=project, year=year, month=month
        )

    def test_price_estimate_in_month_with_service_resource_and_project_is_not_deleted(self):
        self.execute_command()

        self.assertTrue(models.PriceEstimate.objects.filter(id=self.resource_estimate.id).exists())
        self.assertTrue(models.PriceEstimate.objects.filter(id=self.service_estimate.id).exists())
        self.assertTrue(models.PriceEstimate.objects.filter(id=self.project_estimate.id).exists())

    def test_price_estimate_for_service_in_month_without_resource_is_deleted(self):
        self.resource_estimate.delete()

        self.execute_command()
        self.assertFalse(models.PriceEstimate.objects.filter(id=self.service_estimate.id).exists())

    def test_price_estimate_for_invalid_scope_without_details_is_deleted(self):
        self.resource.delete()
        self.resource_estimate.details = ''
        self.resource_estimate.save()

        self.execute_command()
        self.assertFalse(models.PriceEstimate.objects.filter(
            id=self.resource_estimate.id).exists())

    def execute_command(self):
        silent_call('delete_invalid_price_estimates', '--assume-yes')
