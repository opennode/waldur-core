import logging
import calendar
import datetime

from nodeconductor.cost_tracking import CostTrackingStrategy
from nodeconductor.iaas.models import Instance
from nodeconductor.structure import ServiceBackendError


logger = logging.getLogger(__name__)


class IaaSCostTracking(CostTrackingStrategy):

    @classmethod
    def get_costs_estimates(cls, customer=None):
        # TODO: move this logic to IaaS backend method 'get_cost_estimate'
        #       and get rid from app dependent cost tracking together with entry points
        queryset = Instance.objects.exclude(billing_backend_id='')
        if customer:
            queryset = queryset.filter(customer=customer)

        for instance in queryset.iterator():
            try:
                backend = instance.order.backend
                invoice = backend.get_invoice_estimate(instance)
            except ServiceBackendError as e:
                logger.error(
                    "Failed to get price estimate for resource %s: %s", instance, e)
            else:
                today = datetime.date.today()
                if not invoice['start_date'] <= today <= invoice['end_date']:
                    logger.error(
                        "Wrong invoice estimate for resource %s: %s", instance, invoice)
                    continue

                # prorata monthly cost estimate based on daily usage cost
                days_in_month = calendar.monthrange(today.year, today.month)[1]
                daily_cost = invoice['amount'] / ((today - invoice['start_date']).days + 1)
                cost = daily_cost * days_in_month

                yield instance, cost
