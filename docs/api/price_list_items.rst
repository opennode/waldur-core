Price lists
-----------

To get a list of price list items, run GET against **/api/price-list-items/** as authenticated user.


Price lists can be filtered by:
 - ?service=<object URL> URL of service
 - ?resource>=<object URL> URL of resource


Response example:

.. code-block:: http

    GET /api/price-list-items/
    Accept: application/json
    Content-Type: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com


    [
        {
            "url": "http://example.com/api/price-list-items/02033ed510b04fff83e82564f1501fb8/",
            "uuid": "02033ed510b04fff83e82564f1501fb8",
            "key": "oracle-storage",
            "item_type": "storage",
            "value": "0.00000000",
            "units": "",
            "service": "http://example.com/api/oracle/1b883f945ec347c6a0df0ddf1741a394/"
        }
    ]


Manually update price list item
-------------------------------

Run PATCH request against */api/price-list-items/<uuid>/* to update price list item.
Only value and units can be updated. Customer owner and staff can update price estimates.

