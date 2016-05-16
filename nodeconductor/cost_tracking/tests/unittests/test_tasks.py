import unittest

from dateutil.relativedelta import relativedelta

from django.test import TransactionTestCase
from django.utils import timezone

from nodeconductor.cost_tracking.models import PriceEstimate
from nodeconductor.cost_tracking.tasks import update_projected_estimate
from nodeconductor.cost_tracking import CostTrackingBackend
from nodeconductor.structure import models as structure_models
from nodeconductor.structure.tests import factories as structure_factories


@unittest.skip("NC-1392: Test CostTrackingBackend required")
class UpdateProjectedEstimateTest(TransactionTestCase):

    def setUp(self):
        self.customer = structure_factories.CustomerFactory()
        self.project = structure_factories.ProjectFactory(customer=self.customer)
        self.spl1 = structure_factories.TestServiceProjectLinkFactory(project=self.project)
        self.spl2 = structure_factories.TestServiceProjectLinkFactory(project=self.project)

        two_months_ago = timezone.now() - relativedelta(months=+2)
        self.instance1 = structure_factories.TestInstanceFactory(
            service_project_link=self.spl1,
            state=structure_models.Resource.States.ONLINE,
            created=two_months_ago)
        self.instance2 = structure_factories.TestInstanceFactory(
            service_project_link=self.spl2,
            state=structure_models.Resource.States.ONLINE,
            created=two_months_ago)

        # mock estimate calculation task for tests:
        self.INSTANCE_MONTHLY_COST = 10
        CostTrackingBackend.get_monthly_cost_estimate = classmethod(lambda c, i: self.INSTANCE_MONTHLY_COST)

    def test_estimate_calculation_for_current_month_if_parents_has_no_estimates(self):
        update_projected_estimate(customer_uuid=self.customer.uuid.hex)

        now = timezone.now()
        kwargs = {'month': now.month, 'year': now.year}
        self.assertEqual(PriceEstimate.objects.get(scope=self.instance1, **kwargs).total, self.INSTANCE_MONTHLY_COST)
        self.assertEqual(PriceEstimate.objects.get(scope=self.instance2, **kwargs).total, self.INSTANCE_MONTHLY_COST)
        self.assertEqual(PriceEstimate.objects.get(scope=self.spl1, **kwargs).total, self.INSTANCE_MONTHLY_COST)
        self.assertEqual(PriceEstimate.objects.get(scope=self.spl2, **kwargs).total, self.INSTANCE_MONTHLY_COST)
        self.assertEqual(PriceEstimate.objects.get(scope=self.project, **kwargs).total, self.INSTANCE_MONTHLY_COST * 2)
        self.assertEqual(PriceEstimate.objects.get(scope=self.customer, **kwargs).total, self.INSTANCE_MONTHLY_COST * 2)

    def test_estimate_calculation_for_current_month_if_parents_already_have_estimates(self):
        now = timezone.now()
        customer_total = 20
        estimate = PriceEstimate.objects.create(
            scope=self.customer, month=now.month, year=now.year, total=customer_total)

        update_projected_estimate(customer_uuid=self.customer.uuid.hex)

        reread_estimate = PriceEstimate.objects.get(id=estimate.id)
        self.assertEqual(reread_estimate.total, self.INSTANCE_MONTHLY_COST * 2)

    def test_estimate_calculation_for_current_month_if_instance_already_has_estimate(self):
        now = timezone.now()
        instance_total = 20
        estimate = PriceEstimate.objects.create(
            scope=self.instance1, month=now.month, year=now.year, total=instance_total)

        update_projected_estimate(resource_str=self.instance1.to_string())

        reread_estimate = PriceEstimate.objects.get(id=estimate.id)
        self.assertEqual(reread_estimate.total, self.INSTANCE_MONTHLY_COST)

    def test_estimate_calculation_does_not_change_previous_month_estimate_if_it_exists(self):
        month_ago = timezone.now() - relativedelta(months=+1)
        instance_total = 20
        customer_total = instance_total * 2
        instance1_estimate = PriceEstimate.objects.create(
            scope=self.instance1, month=month_ago.month, year=month_ago.year, total=instance_total)
        instance2_estimate = PriceEstimate.objects.create(
            scope=self.instance2, month=month_ago.month, year=month_ago.year, total=instance_total)
        customer_estimate = PriceEstimate.objects.create(
            scope=self.customer, month=month_ago.month, year=month_ago.year, total=customer_total)

        update_projected_estimate(customer_uuid=self.customer.uuid.hex)

        reread_instance1_estimate = PriceEstimate.objects.get(id=instance1_estimate.id)
        self.assertEqual(reread_instance1_estimate.total, instance_total)
        reread_instance2_estimate = PriceEstimate.objects.get(id=instance2_estimate.id)
        self.assertEqual(reread_instance2_estimate.total, instance_total)
        reread_customer_estimate = PriceEstimate.objects.get(id=customer_estimate.id)
        self.assertEqual(reread_customer_estimate.total, customer_total)

    def test_estimate_calculation_creates_estimates_for_previous_monthes_if_it_does_not_exist(self):
        update_projected_estimate(customer_uuid=self.customer.uuid.hex)

        month_ago = timezone.now() - relativedelta(months=+1)
        kwargs = {'month': month_ago.month, 'year': month_ago.year}
        self.assertEqual(PriceEstimate.objects.get(scope=self.instance1, **kwargs).total, self.INSTANCE_MONTHLY_COST)
        self.assertEqual(PriceEstimate.objects.get(scope=self.instance2, **kwargs).total, self.INSTANCE_MONTHLY_COST)
        self.assertEqual(PriceEstimate.objects.get(scope=self.spl1, **kwargs).total, self.INSTANCE_MONTHLY_COST)
        self.assertEqual(PriceEstimate.objects.get(scope=self.spl2, **kwargs).total, self.INSTANCE_MONTHLY_COST)
        self.assertEqual(PriceEstimate.objects.get(scope=self.project, **kwargs).total, self.INSTANCE_MONTHLY_COST * 2)
        self.assertEqual(PriceEstimate.objects.get(scope=self.customer, **kwargs).total, self.INSTANCE_MONTHLY_COST * 2)
