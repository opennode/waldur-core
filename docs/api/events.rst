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
- ?exclude_features=<feature> (can be list) - exclude event from output if it's type corresponds to one of listed features

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


Create an event
---------------

Run POST against */api/events/* to create an event. Only users with staff privileges can create events.
New event will be emitted with `custom_notification` event type.
Request should contain following fields:

- level: the level of current event. Following levels are supported: debug, info, warning, error
- message: string representation of event message
- scope_url: optional URL field

Request example:

.. code-block:: javascript

    POST /api/events/
    Accept: application/json
    Content-Type: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "level": "info",
        "message": "message#1",
        "scope_url": "http://example.com"
    }


Hooks
-----

Hooks API allows user to receive event notifications via different channel, like email or webhook.

To get a list of all your hooks, run GET against **/api/hooks/** as an authenticated user. Example of a response:

.. code-block:: javascript

    [
        {
            "url": "http://example.com/api/hooks/81ad8f069202487cbd87cda843d27d6a/",
            "uuid": "81ad8f069202487cbd87cda843d27d6a",
            "is_active": true,
            "author_uuid": "1c3323fc4ae44120b57ec40dea1be6e6",
            "created": "2015-07-09T13:22:11.301Z",
            "modified": "2015-07-09T13:22:11.303Z",
            "events": [
                "iaas_instance_start_succeeded"
            ],
            "destination_url": "http://example.com",
            "content_type": "json",
            "hook_type": "webhook"
        }
    ]

To create new web hook issue POST against **/api/hooks-web/** as an authenticated user.
Request should contain fields:

- events: list of event types you are interested in
- destination_url: valid URL endpoint
- content_type: optional value, which may be "json" or "form", default is "json"

When hook is activated, POST request is issued against destination URL with the following data:

.. code-block:: javascript

    {
        "timestamp": "2015-07-14T12:12:56.000000",
        "message": "Customer ABC LLC has been updated.",
        "type": "customer_update_succeeded",
        "context": {
            "user_native_name": "Walter Leb\u00f6wski",
            "customer_contact_details": "",
            "user_username": "Walter",
            "user_uuid": "1c3323fc4ae44120b57ec40dea1be6e6",
            "customer_uuid": "4633bbbb0b3a4b91bffc0e18f853de85",
            "ip_address": "8.8.8.8",
            "user_full_name": "Walter Lebowski",
            "customer_abbreviation": "ABC LLC",
            "customer_name": "ABC LLC"
        },
        "levelname": "INFO"
    }

Note that context depends on event type.

To create new email hook issue POST against **/api/hooks-email/** as an authenticated user.
Request should contain fields:

- events: list of event types you are interested in
- email: destination email address

Example of a request:

.. code-block:: javascript

    {
        "events": [
            "iaas_instance_start_succeeded"
        ],
        "email": "test@example.com"
    }

You may temporarily disable hook without deleting it by issuing following PATCH request against hook URL:

.. code-block:: javascript

    {
        "is_active": "false"
    }
