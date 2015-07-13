Events list
-------------

To get a list of events, run GET against **/api/events/** as authenticated user. Note that a user can
only see events connected to objects she is allowed to see.

Sorting is supported in ascending and descending order by specifying a field to an **?o=** parameter. By default
events are sorted by @timestamp in descending order.

- ?o=\@timestamp

Filtering of customer list is supported through HTTP query parameters, the following fields are supported:

- ?event_type=<event_type> - type of filtered events. Can be list.
- ?search - text for FTS. FTS fields: 'message', 'customer_abbreviation', 'importance',
  'project_group_name', 'cloud_account_name', 'project_name'
- ?project_uuid=<project_uuid>
- ?customer_uuid=<customer_uuid>
- ?project_group_uuid=<project_group_uuid>
- ?user_uuid=<user_uuid>


Hooks
-----

Hooks API allows user to receive event notifications via different channel, like email or webhook.
To get a list of your web hooks, run GET against **/api/hooks-web/** as an authenticated user.
Example of a response:

.. code-block:: javascript

    [
        {
            "url": "http://example.com/api/hooks/81ad8f069202487cbd87cda843d27d6a/",
            "uuid": "81ad8f069202487cbd87cda843d27d6a",
            "is_active": true,
            "author_uuid": "1c3323fc4ae44120b57ec40dea1be6e6",
            "last_published": "2015-07-09T13:22:11.301Z",
            "created": "2015-07-09T13:22:11.301Z",
            "modified": "2015-07-09T13:22:11.303Z",
            "events": [
                "iaas_instance_start_succeeded"
            ],
            "url": "http://example.com",
            "content_type": "json"
        }
    ]

To create new web hook issue POST against **/api/hooks-web/** as an authenticated user.
Request should contain fields:

- events: list of event types you are interested in
- url: destination URL for webhook
- content_type: optional value, which may be "json" or "form", default is "json"

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
