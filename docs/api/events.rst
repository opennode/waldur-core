Events list
-----------

To get a list of events - run GET against **/api/events/** as authenticated user. Note that a user can
only see events connected to objects she is allowed to see.

Sorting is supported in ascending and descending order by specifying a field to an **?o=** parameter. By default
events are sorted by @timestamp in descending order.

- ?o=\@timestamp

Filtering of customer list is supported through HTTP query parameters, the following fields are supported:

- ?event_type=<string> - type of filtered events. Can be list
- ?search=<string> - text for FTS. FTS fields: 'message', 'customer_abbreviation', 'importance'
  'project_group_name', 'cloud_account_name', 'project_name'
- ?scope=<URL> - url of object that is connected to event
- ?scope_type=<string> - name of scope type of object that is connected to event (Ex.: project, customer...)


Events count
------------

To get a count of events - run GET against **/api/events/count/** as authenticated user. Endpoint support same filters
as events list.

Response example:

.. code-block:: javascript

    {"count": 12321}


Events count history
--------------------

To get a historical data of events amount - run GET against **/api/events/count/history/**. Endpoint support same
filters as events list. More about historical data - read at section *Historical data*.


Response example:

.. code-block:: javascript

    [
        {
            "point": 141111111111,
            "object": {
                "count": 558
            }
        }
    ]
