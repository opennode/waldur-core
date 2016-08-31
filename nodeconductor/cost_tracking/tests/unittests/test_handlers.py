import datetime

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone
from freezegun import freeze_time

from nodeconductor.cost_tracking import CostTrackingRegister, models, ConsumableItem
from nodeconductor.cost_tracking.tests import factories
from nodeconductor.structure.tests import factories as structure_factories
from nodeconductor.structure.tests.models import TestNewInstance


class ResourceUpdateTest(TestCase):

    def setUp(self):
        CostTrackingRegister.register_strategy(factories.TestNewInstanceCostTrackingStrategy)

    @freeze_time('2016-08-08 11:00:00', tick=True)  # freeze time to avoid bugs in the end of a month.
    def test_consumption_details_of_resource_is_keeped_up_to_date(self):
        today = timezone.now()
        configuration = dict(ram=2048, disk=20 * 1024, cores=2)
        resource = structure_factories.TestNewInstanceFactory(
            state=TestNewInstance.States.OK, runtime_state='online', **configuration)

        price_estimate = models.PriceEstimate.objects.get(scope=resource, month=today.month, year=today.year)
        consumption_details = price_estimate.consumption_details
        expected = {
            ConsumableItem('ram', '1 MB'): 2048,
            ConsumableItem('storage', '1 MB'): 20 * 1024,
            ConsumableItem('cores', '1 core'): 2,
            ConsumableItem('quotas', 'test_quota'): 0,
        }
        self.assertDictEqual(consumption_details.configuration, expected)

        resource.ram = 1024
        resource.save()
        consumption_details.refresh_from_db()
        self.assertEqual(consumption_details.configuration[ConsumableItem('ram', '1 MB')], resource.ram)

        resource.runtime_state = 'offline'
        resource.save()
        # test resource uses only storage and quota when it is offline
        expected = {
            ConsumableItem('storage', '1 MB'): 20 * 1024,
            ConsumableItem('quotas', 'test_quota'): 0
        }
        consumption_details.refresh_from_db()
        self.assertDictEqual(consumption_details.configuration, expected)

        resource.flavor_name = 'small'
        resource.save()
        consumption_details.refresh_from_db()
        self.assertEqual(consumption_details.configuration[ConsumableItem('flavor', 'small')], 1)

    def test_price_estimate_of_resource_is_keeped_up_to_date(self):
        resource_content_type = ContentType.objects.get_for_model(TestNewInstance)
        price_list_item = models.DefaultPriceListItem.objects.create(
            item_type='storage', key='1 MB', resource_content_type=resource_content_type)
        price_list_item.value = 0.5
        price_list_item.save()

        start_time = datetime.datetime(2016, 8, 8, 11, 0)
        with freeze_time(start_time):
            today = timezone.now()
            old_disk = 20 * 1024
            resource = structure_factories.TestNewInstanceFactory(
                state=TestNewInstance.States.OK, runtime_state='online', disk=old_disk)
            price_estimate = models.PriceEstimate.objects.get(scope=resource, month=today.month, year=today.year)
            # after resource creation price estimate should be calculate for whole month
            month_end = datetime.datetime(2016, 8, 31, 23, 59, 59)
            expected = (
                int((month_end - start_time).total_seconds() / 60) * price_list_item.minute_rate * old_disk)
            self.assertAlmostEqual(price_estimate.total, expected)

        # after some time resource disk was updated - resource price should be recalculated
        change_time = datetime.datetime(2016, 8, 9, 13, 0)
        with freeze_time(change_time):
            new_disk = 40 * 1024
            resource.disk = new_disk
            resource.save()

            price_estimate.refresh_from_db()
            expected = (
                int((change_time - start_time).total_seconds() / 60) * price_list_item.minute_rate * old_disk +
                int((month_end - change_time).total_seconds() / 60) * price_list_item.minute_rate * new_disk)
            self.assertAlmostEqual(price_estimate.total, expected)

    def test_price_estimate_of_resource_ancestors_is_keeped_up_to_date(self):
        """ On resource configuration tests handlers should update resource ancestors estimates """
        resource_content_type = ContentType.objects.get_for_model(TestNewInstance)
        price_list_item = models.DefaultPriceListItem.objects.create(
            item_type='storage', key='1 MB', resource_content_type=resource_content_type)
        price_list_item.value = 0.5
        price_list_item.save()

        start_time = datetime.datetime(2016, 8, 8, 11, 0)
        with freeze_time(start_time):
            today = timezone.now()
            old_disk = 20 * 1024
            resource = structure_factories.TestNewInstanceFactory(
                state=TestNewInstance.States.OK, runtime_state='online', disk=old_disk)
            ancestors = [resource.service_project_link, resource.service_project_link.service,
                         resource.service_project_link.project, resource.service_project_link.project.customer]
            # after resource creation price for it ancestors should be calculate for whole month
            month_end = datetime.datetime(2016, 8, 31, 23, 59, 59)
            expected = (
                int((month_end - start_time).total_seconds() / 60) * price_list_item.minute_rate * old_disk)
            for ancestor in ancestors:
                ancestor_estimate = models.PriceEstimate.objects.get(scope=ancestor, month=today.month, year=today.year)
                self.assertAlmostEqual(ancestor_estimate.total, expected)

        # after some time resource disk was updated - resource ancestors price should be recalculated
        change_time = datetime.datetime(2016, 8, 9, 13, 0)
        with freeze_time(change_time):
            new_disk = 40 * 1024
            resource.disk = new_disk
            resource.save()

            expected = (
                int((change_time - start_time).total_seconds() / 60) * price_list_item.minute_rate * old_disk +
                int((month_end - change_time).total_seconds() / 60) * price_list_item.minute_rate * new_disk)
            for ancestor in ancestors:
                ancestor_estimate = models.PriceEstimate.objects.get(scope=ancestor, month=today.month, year=today.year)
                self.assertAlmostEqual(ancestor_estimate.total, expected)


class ResourceQuotaUpdateTest(TestCase):

    def setUp(self):
        CostTrackingRegister.register_strategy(factories.TestNewInstanceCostTrackingStrategy)

    @freeze_time('2016-08-08 11:00:00', tick=True)  # freeze time to avoid bugs in the end of a month.
    def test_consumption_details_of_resource_is_keeped_up_to_date_on_quota_change(self):
        today = timezone.now()
        resource = structure_factories.TestNewInstanceFactory()
        quota_item = ConsumableItem('quotas', 'test_quota')

        price_estimate = models.PriceEstimate.objects.get(scope=resource, month=today.month, year=today.year)
        consumption_details = price_estimate.consumption_details
        self.assertEqual(consumption_details.configuration[quota_item], 0)

        resource.set_quota_usage(TestNewInstance.Quotas.test_quota, 5)

        consumption_details.refresh_from_db()
        self.assertEqual(consumption_details.configuration[quota_item], 5)


@freeze_time('2016-08-08 13:00:00')
class ScopeDeleteTest(TestCase):

    def setUp(self):
        resource_content_type = ContentType.objects.get_for_model(TestNewInstance)
        self.price_list_item = models.DefaultPriceListItem.objects.create(
            item_type='storage', key='1 MB', resource_content_type=resource_content_type)
        CostTrackingRegister.register_strategy(factories.TestNewInstanceCostTrackingStrategy)
        self.start_time = datetime.datetime(2016, 8, 8, 11, 0)
        with freeze_time(self.start_time):
            self.resource = structure_factories.TestNewInstanceFactory(disk=20 * 1024)
        self.spl = self.resource.service_project_link
        self.project = self.spl.project
        self.customer = self.project.customer
        self.service = self.spl.service

    def test_all_estimates_are_deleted_on_customer_deletion(self):
        self.resource.delete()
        self.project.delete()
        self.customer.delete()

        for scope in (self.spl, self.resource, self.service, self.project, self.customer):
            self.assertFalse(models.PriceEstimate.objects.filter(scope=scope).exists(),
                             'Unexpected price estimate exists for %s %s' % (scope.__class__.__name__, scope))

    def test_estimate_is_recalculated_on_resource_deletion(self):
        self.resource.delete()

        expected = 2 * self.price_list_item.value * self.resource.disk  # resource has been working for 2 hours
        for scope in (self.spl, self.service, self.project, self.customer):
            self.assertEqual(models.PriceEstimate.objects.get_current(scope).total, expected)

    def test_estimate_populate_details_on_scope_deletion(self):
        scopes = (self.resource, self.service, self.project)
        for scope in scopes:
            estimate = models.PriceEstimate.objects.get_current(scope)
            scope.delete()
            estimate.refresh_from_db()

            self.assertEqual(estimate.details['name'], scope.name)
