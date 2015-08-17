import logging

from nodeconductor.cost_tracking import CostTrackingStrategy
from nodeconductor.structure.models import Customer

logger = logging.getLogger(__name__)


class IaaSCostTracking(CostTrackingStrategy):

    @classmethod
    def get_costs_estimates(cls, customer=None):
        if customer:
            customers = [customer]
        else:
            customers = Customer.objects.exclude(billing_backend_id='').iterator()

        for customer in customers:
            try:
                backend = customer.get_billing_backend()
                monthly_cost = backend.get_total_cost_of_active_products()
            except:
                logger.error(
                    "Failed to get price estimate for customer %s "
                    "with existing billing backend id. Stale customer?" % customer)
            else:
                yield customer, monthly_cost
