from unittest import skip

import mock
from django.utils import timezone
from rest_framework import test

from nodeconductor.cost_tracking.exceptions import CostLimitExceeded
from nodeconductor.cost_tracking.models import PriceEstimate
from nodeconductor.structure.tests import factories as structure_factories


@skip('Should be fixed or rewritten in NC-1537')
class TestProjectCostLimit(test.APITransactionTestCase):
    """
    If total cost of project and resource exceeds cost limit provision is disabled.
    """
    def test_if_total_cost_of_project_and_resource_exceeds_cost_limit_provision_is_disabled(self):
        project = self.create_project(limit=100, total=70)
        with self.assertRaises(CostLimitExceeded):
            self.create_resource(project, cost=50)

    def test_total_cost_is_ok(self):
        project = self.create_project(limit=100, total=70)
        self.create_resource(project, cost=20)

    def create_project(self, limit, total):
        project = structure_factories.ProjectFactory()
        dt = timezone.now()
        PriceEstimate.objects.create(scope=project, year=dt.year, month=dt.month, limit=limit, total=total)
        return project

    def create_resource(self, project, cost):
        link = structure_factories.TestServiceProjectLinkFactory(project=project)
        with mock.patch('nodeconductor.cost_tracking.handlers.CostTrackingRegister') as register:
            register.get_resource_backend().get_monthly_cost_estimate.return_value = cost
            structure_factories.TestNewInstanceFactory(service_project_link=link)
