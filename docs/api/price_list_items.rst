Price list items
----------------

To get a list of price list items, run GET against **/api/price-list-items/** as authenticated user.


Price lists can be filtered by:
 - ?service=<object URL> URL of service


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
            "key": "1 GB",
            "item_type": "storage",
            "value": "0.99",
            "units": "USD",
            "service": "http://example.com/api/oracle/1b883f945ec347c6a0df0ddf1741a394/"
        }
    ]


Create price list item
----------------------

Run POST request */api/price-list-items/* to create new price list item.
Customer owner and staff can create price estimates.

Example of request:

.. code-block:: http

    POST /api/customers/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "units": "per month",
        "key": "test_key",
        "value": 100,
        "service": "http://testserver/api/oracle/d4060812ca5d4de390e0d7a5062d99f6/",
        "item_type": "storage"
    }


Update price list item
----------------------

Run PATCH request against */api/price-list-items/<uuid>/* to update price list item.
Only value and units can be updated. Customer owner and staff can update price estimates.


Delete price list item
----------------------

Run DELETE request against */api/price-list-items/<uuid>/* to delete price list item.
Customer owner and staff can delete price estimates.
