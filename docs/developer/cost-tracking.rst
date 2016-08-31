Cost tracking
=============

Add-on for NodeConductor plugins. It allows to calculate price estimates for resources.


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
        def get_configuration(cls, resource):
            # which consumables are used by resource
            return {
                ConsumableItem(cls.Types.FLAVOR, resource.flavor_name): 1,
                ConsumableItem(cls.Types.STORAGE, '1 MB'): resource.disk,
            }

        @classmethod
        def get_consumable_items(cls):
            return [
                ConsumableItem(cls.Types.STORAGE, "1 MB", units='MB', name='Storage'),
                ConsumableItem(cls.Types.FLAVOR, "small", name='Small flavor'),
                ConsumableItem(cls.Types.FLAVOR, "medium", name='Medium flavor'),
                ConsumableItem(cls.Types.FLAVOR, "large", name='Large flavor'),
            ]

2. Register Strategy in CostTrackingRegister.

.. code-block::python

    CostTrackingRegister.register_strategy(factories.TestNewInstanceCostTrackingStrategy)


How total estimate calculation works
------------------------------------

Total price estimate - price of the consumables that resource will use in a month.

Total price estimate is calculated for all registered resources and their
structure objects: SPLs, projects, services, service settings, customers.

Module "cost_tracking" connects to Django signals to keep resource estimate and 
consumption details up to date (check the code of the handlers for more details).
Model "ConsumptionDetails" stores current resource configuration and how many
consumables were used by a resource. On each configuration update module updates
consumption details and recalculates price estimates for resource and all his 
ancestors.


How consumed estimate calculation works
---------------------------------------

Consumed price estimate - how many consumables were used by resource until now.

It is too expensive to recalculate consumed estimate on each user request.
Thats why we have the background task that recalculate consumed estimate every
hour and stores it in the database.
