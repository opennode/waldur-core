"""
Cost tracking - add-on for NC plugins.


Add-on adds next functional to plugin:

 - calculate and store price estimate for each resource, service, project, customer.
 - register resource used items (ex: CPU, storage for VMs) prices and show their prices for resource cost calculation.
 - get resource used items for current moment.


Add-on connection:

    1. Implement CostTrackingBackend interface.

        class IaaSCostTrackingBackend(CostTrackingBackend):
            ...

    2. Add application to add-on register.

        CostTrackingRegister.register(self.label, cost_tracking.IaaSCostTrackingBackend)

"""

default_app_config = 'nodeconductor.cost_tracking.apps.CostTrackingConfig'


class CostTrackingRegister(object):
    """ Register of all connected NC plugins """

    _register = {}

    @classmethod
    def register(cls, app_label, backend):
        cls._register[app_label] = backend

    @classmethod
    def get_registered_backends(cls):
        return cls._register.values()

    @classmethod
    def get_resource_backend(cls, resource):
        return cls._register.get(resource._meta.app_label)


class CostTrackingBackend(object):
    """ Cost tracking interface for NC plugin """

    @classmethod
    def get_used_items(cls, resource):
        """ Return list of items that are currently used by resource

        Return format: [(<item type>, <item name>, <item usage>), ...]
        <item usage> should be 1 for all uncountable items (flavors, installed OS ...)
        """
        raise NotImplementedError()

    @classmethod
    def get_service_price_list_items(cls, service):
        """ Return list of price items for concrete service """
        raise NotImplementedError()

    @classmethod
    def get_default_price_list_items(cls):
        """ Return list of default price items for application """
        raise NotImplementedError()

    @classmethod
    def get_monthly_cost_estimate(cls, resource):
        """ Get resource monthly cost estimate """
        # TODO: implement monthly cost estimate calculation based on items prices and used items.
        raise NotImplementedError()
