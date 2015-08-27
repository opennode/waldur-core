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
                # prorata estimate calculation based on daily usage cost
                sd = invoice['start_date']
                ed = invoice['end_date']
                today = datetime.date.today()
                if not sd <= today <= ed:
                    logger.error(
                        "Wrong invoice estimate for resource %s: %s", instance, invoice)
                    continue

                if sd.year == today.year and sd.month == today.month:
                    days_in_month = calendar.monthrange(sd.year, sd.month)[1]
                    days = sd.replace(day=days_in_month) - sd

                elif ed.year == today.year and ed.month == today.month:
                    days = ed - ed.replace(day=1)

                daily_cost = invoice['amount'] / ((today - sd).days + 1)
                cost = daily_cost * (days.days + 1)

                yield instance, cost
