from . import models
from nodeconductor.cost_tracking import CostTrackingBackend


class OpenStackCostTrackingBackend(CostTrackingBackend):

    @classmethod
    def get_monthly_cost_estimate(cls, resource):
        backend = resource.get_backend()
        return backend.get_monthly_cost_estimate(resource)
