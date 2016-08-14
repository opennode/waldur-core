import datetime

from django.test import TestCase
from freezegun import freeze_time

from nodeconductor.cost_tracking import models
from nodeconductor.cost_tracking.tests import factories


class ConsumptionDetailsTest(TestCase):

    def setUp(self):
        price_estimate = factories.PriceEstimateFactory(year=2016, month=8)
        self.consumption_details = factories.ConsumptionDetailsFactory(price_estimate=price_estimate)

    def test_current_configuration_update(self):
        """ Test that consumed_before_modification field stores consumed items on configuration update """
        # Resource used some consumables
        with freeze_time("2016-08-08 11:00:00"):
            old_configuration = {'storage': 1024, 'ram': 512}
            self.consumption_details.update_configuration(old_configuration)
        # After 2 hours resource configuration was updated
        with freeze_time("2016-08-08 13:00:00"):
            self.consumption_details.update_configuration({'storage': 2048})
        # Details of consumed items should be stored
        HOURS_BEFORE_UPDATE = 2
        for consumable, usage in old_configuration.items():
            self.assertEqual(self.consumption_details.consumed_before_update[consumable],
                             old_configuration[consumable] * HOURS_BEFORE_UPDATE * 60)

    def test_cannot_update_configuration_for_previous_month(self):
        with freeze_time("2016-09-01"):
            self.assertRaises(
                models.ConsumptionDetailUpdateError,
                lambda: self.consumption_details.update_configuration({'storage': 2048}))

    def test_consumed(self):
        """ Property "consumed" should return how much consumables resource will use for whole month """
        # Resource used some consumables
        start_time = datetime.datetime(2016, 8, 8, 11, 0)
        with freeze_time(start_time):
            old_configuration = {'storage': 1024}
            self.consumption_details.update_configuration(old_configuration)
        # After 2 hours resource configuration was updated
        change_time = datetime.datetime(2016, 8, 8, 13, 0)
        with freeze_time(change_time):
            new_configuration = {'storage': 2048}
            self.consumption_details.update_configuration(new_configuration)

        # Expected consumption should assume that resource will use current
        # configuration to the end of month and add 2 hours of old configuration
        month_end = datetime.datetime(2016, 8, 31, 23, 59, 59)
        expected = (int((change_time - start_time).total_seconds() / 60) * old_configuration['storage'] +
                    int((month_end - change_time).total_seconds() / 60) * new_configuration['storage'])
        self.assertEqual(self.consumption_details.consumed['storage'], expected)
