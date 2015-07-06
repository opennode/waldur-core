Historical data
---------------

Historical data endpoints could be available for any objects (currently
implemented for quotas only). The data is available at **<object_endpoint>/history/**,
for example: **/api/quotas/<uuid>/history/**.

There are two ways to define datetime points for historical data.

1. Send *?point=<timestamp>* parameter that can list. Response will contain historical data for each given point in the
   same order.
2. Send *?start=<timestamp>*, *?end=<timestamp>*, *?points_count=<integer>* parameters.
   Result will contain <points_count> points from <start> to <end>.

Response format:

.. code-block:: javascript

    [
        {
            "point": <timestamp>,
            "object": {<object_representation>}
        },
        {
            "point": <timestamp>
            "object": {<object_representation>}
        },
    ...
    ]

NB! There will not be any "object" for corresponding point in response if there
is no data about object for a given timestamp.

Response example:

.. code-block:: http

    GET api/quotas/4080f44763b84a9c83a0983f3b025b23/history/?point=1436094582&point=143000000 HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    [
        {
            "point": 1436094582,
            "object": {
                "url": "http://example.com/api/quotas/4080f44763b84a9c83a0983f3b025b23/",
                "uuid": "4080f44763b84a9c83a0983f3b025b23",
                "name": "some_quota",
                "limit": -1.0,
                "usage": 52.0,
                "scope": "http://example.com/api/customers/53c6e86406e349faa7924f4c865b15ab/"
            },
        },
        {
            "point": 143000000
        },
    ...
    ]
