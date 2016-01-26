Default price list items
------------------------

To get a list of default price list items, run GET against **/api/default-price-list-items/** as authenticated user.

Price lists can be filtered by:
 - ?key=<string>
 - ?item_type=<string> has to be from list of available item_types
   (available options: 'flavor', 'storage', 'license-os', 'license-application', 'network', 'support')
 - ?resource_type==<string> resource type, for example: 'OpenStack.Instance, 'Oracle.Database')


Response example:

.. code-block:: http

    GET /api/default-price-list-items/
    Accept: application/json
    Content-Type: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    [
        {
            "url": "http://example.com/api/default-price-list-items/0feeeb57033e41acb8ad2ae2b914e9b0/",
            "uuid": "0feeeb57033e41acb8ad2ae2b914e9b0",
            "key": "t1.micro",
            "item_type": "flavor",
            "value": 0.02,
            "resource_type": "Amazon.Instance",
            "metadata": {
                "disk": 15,
                "ram": 613,
                "name": "Micro Instance"
            }
        },
        {
            "url": "http://example.com/api/default-price-list-items/5c637a7131a24300bc422526decc20c3/",
            "uuid": "5c637a7131a24300bc422526decc20c3",
            "key": "wordpress",
            "item_type": "license-application",
            "value": 4.0,
            "resource_type": "IaaS.Instance",
            "metadata": ""
        }
    ]
