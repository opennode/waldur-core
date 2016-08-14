from django.test import TestCase
from freezegun import freeze_time

from nodeconductor.cost_tracking import models
from nodeconductor.cost_tracking.tests import factories


class ConsumptionDetailsManagerTest(TestCase):

    def test_create_method_get_configuration_from_previous_month_details(self):
        with freeze_time("2016-08-01"):
            configuration = {'storage': 10240, 'ram': 2048}
            price_estimate = factories.PriceEstimateFactory(year=2016, month=8)
            consumption_details = factories.ConsumptionDetailsFactory(price_estimate=price_estimate)
            consumption_details.update_configuration(configuration)

        with freeze_time("2016-09-01"):
            next_price_estimate = models.PriceEstimate.objects.create(
                scope=price_estimate.scope,
                month=price_estimate.month + 1,
                year=price_estimate.year,
            )
            next_consumption_details = models.ConsumptionDetails.objects.create(price_estimate=next_price_estimate)
        self.assertDictEqual(next_consumption_details.configuration, configuration)
