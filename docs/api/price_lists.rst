Price lists
-----------

To get a list of price lists, run GET against **/api/price-list/** as authenticated user.


Price lists can be filtered by:
 - ?service=<object URL> URL of service


Response example:

.. code-block:: http

    GET /api/price-list/
    Accept: application/json
    Content-Type: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com


    [
        {
            "url": "http://example.com/api/price-list/5eb6ab7eb2074f269f13605a20ab1f18/",
            "uuid": "5eb6ab7eb2074f269f13605a20ab1f18",
            "service": "http://example.com/api/oracle/8eb40b9976b24e03aa76bfd828316c14/",
            "items": [
                {
                    "name": "cpu",
                    "value": 10.0,
                    "units": ""
                },
                {
                    "name": "memory",
                    "value": 100.0,
                    "units": "GB/H"
                }
            ]
        }
    ]


Manually create price list
--------------------------

Run POST against */api/price-list/* to create price list for service. One service cannot have more then one price list.
Only customer owner and staff can update price list.

Request example:

.. code-block:: javascript

    POST /api/price-list/
    Accept: application/json
    Content-Type: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "service": "http://example.com/api/oracle/8eb40b9976b24e03aa76bfd828316c14/",
        "items": [
            {
                "name": "cpu",
                "value": 20.0,
                "units": ""
            },
            {
                "name": "memory",
                "value": 200.0,
                "units": "GB/H"
            }
        ]
    }


Update manually created price list
----------------------------------

Run PATCH request against */api/price-list/<uuid>/* to update manually created price list.
Only customer owner and staff can update price estimates.


Delete manually created price list
--------------------------------------

Run DELETE request against */api/price-list/<uuid>/* to delete price list.
Only customer owner and staff can delete price list.

