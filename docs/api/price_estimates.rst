Price estimates
---------------

To get a list of price estimates, run GET against **/api/price-estimates/** as authenticated user.


Price estimates can be filtered by:
 - ?scope=<object URL> URL of object that was estimated
 - ?scope_type=<string> can be list. Filter by scope type
 - ?date=<string in format YYYY.MM> can be list. Filters price estimates for given months
 - ?start=<string in format YYYY.MM> filter price estimates that was after given months (excluding given)
 - ?end=<string in format YYYY.MM> filter price estimates that was before end months (including given)
 - ?is_manually_input=True|False - show manually created (auto calculated) estimates
 - ?customer=<UUID> - filter price estimates by objects connected to a specific customer

Price estimates in response are sorted from latest to earliest.


.. code-block:: http

    GET /api/price-estimates/
    Accept: application/json
    Content-Type: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    [
        {
            "url": "http://example.com/api/price-estimates/3c3542c614a744df961fea8dc13e3d7c/",
            "uuid": "3c3542c614a744df961fea8dc13e3d7c",
            "scope": "http://example.com/api/instances/0424c7746059458ab9a5ad4d097c1d31/",
            "scope_name": "Example Virtual Machine #100",
            "scope_type": "resource",
            "resource_type": "OpenStack.Instance",
            "total": 1114.0,
            "consumed": 1027.0,
            "month": 7,
            "year": 2015,
            "is_manually_inputed": false
        },
    ]

scope_type is generic type of object for which price estimate is calculated. Currently there are following types: customer, project, serviceprojectlink, service, resource.


Manually create price estimate
------------------------------

Run POST against */api/price-estimates/* to create price estimate. Manually created price estimate will replace
auto calculated estimate. Manual creation is available only for estimates for resources and service-project-links.
Only customer owner and staff can edit price estimates.

Request example:

.. code-block:: javascript

    POST /api/price-estimates/
    Accept: application/json
    Content-Type: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "scope": "http://example.com/api/instances/ab2e3d458e8a4ecb9dded36f3e46878d/",
        "total": 1000,
        "consumed": 800,
        "month": 8,
        "year": 2015
    }


Update manually created price estimate
--------------------------------------

Run PATCH request against */api/price-estimates/<uuid>/* to update manually created price estimate. Only fields "total"
and "consumed" could be updated. Only customer owner and staff can update price estimates.


Delete manually created price estimate
--------------------------------------

Run DELETE request against */api/price-estimates/<uuid>/* to delete price estimate. Estimate will be
replaced with auto calculated (if it exists). Only customer owner and staff can delete price estimates.

