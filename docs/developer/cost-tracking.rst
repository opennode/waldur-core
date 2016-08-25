Cost tracking
=============

Add-on for NC plugins. It allows to calculate price estimates for resources.


How to use
----------

1. Define CostTrackingStrategy for resource. Example:

.. code-block::python

    class TestNewInstanceCostTrackingStrategy(CostTrackingStrategy):
        resource_class = test_models.TestNewInstance  # define resource class

        class Types(object):  # consumable types.
            STORAGE = 'storage'
            FLAVOR = 'flavor'

        @classmethod
        def get_consumables(cls, resource):
            # which consumables are used by resource
            return {
                '%s: %s' % (cls.Types.FLAVOR, resource.flavor_name): 1,
                '%s: 1 MB' % cls.Types.STORAGE: resource.disk,
            }

        @classmethod
        def get_consumables_default_prices(cls):
            return [
                {"item_type": cls.Types.STORAGE, "key": "1 MB", "units": "MB", "rate": 0.5, "name": "Storage"},
                {"item_type": cls.Types.FLAVOR, "key": "small", "units": "", "rate": 20, "name": "Small flavor"},
                {"item_type": cls.Types.FLAVOR, "key": "medium", "units": "", "rate": 40, "name": "Medium flavor"},
                {"item_type": cls.Types.FLAVOR, "key": "large", "units": "", "rate": 60, "name": "Large flavor"},
            ]

2. Register Strategy in CostTrackingRegister.

.. code-block::python

    CostTrackingRegister.register_strategy(factories.TestNewInstanceCostTrackingStrategy)


How total estimate calculation works
------------------------------------

Total price estimate - price of the consumables that resource will in a month.

Total price estimate is calculated for all registered resources and their
structure objects: SPLs, projects, services, service settings, customers.

Module "cost_tracking" connects to django signals to keep resource estimate and 
consumption details up to date (check the code of the handlers for more details).
Model "ConsuptionDetails" stores current resource configuration and how many
consumables were used by a resource. On each configuration update module updates
resource consumption details and recalculates price estimate.


How consumed estimate calculation works
---------------------------------------

Consumed price estimate - how many consumables were used by resource until now.

It is too expensive to recalculate consumed estimate on each user request.
Thats why we have the background task that recalculate consumed estimate every
hour and stores it in the database.
