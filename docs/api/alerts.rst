Alerts
------

To get a list of alerts, run GET against **/api/alerts/** as authenticated user.

Alert severity field can take one of this values: "Error", "Warning", "Info", "Debug".
Field scope will contain link to object that cause alert.
Context - dictionary that contains information about all related to alert objects.

Alerts can be filtered by:
 - ?severity=<severity> (can be list)
 - ?alert_type=<alert_type> (can be list)
 - ?scope=<url> concrete alert scope
 - ?scope_type=<string> name of scope type (Ex.: instance, cloud_project_membership, project...)
 - ?created_from=<timestamp>
 - ?created_to=<timestamp>
 - ?closed_from=<timestamp>
 - ?closed_to=<timestamp>
 - ?from=<timestamp> - filter alerts that was active from given date
 - ?to=<timestamp> - filter alerts that was active to given date
 - ?opened - if this argument is in GET request endpoint will return only alerts that are not closed
 - ?aggregate=aggregate_model_name (default: 'customer'. Have to be from list: 'customer', 'project', 'project_group')
 - ?uuid=uuid_of_aggregate_model_object (not required. If this parameter will be defined - result will contain only
   object with given uuid)
 - ?acknowledged=True|False - show only acknowledged (non-acknowledged) alerts

Alerts can be ordered by:

 -?o=severity - order by severity
 -?o=created - order by creation time


.. code-block:: http

    GET /api/alerts/
    Accept: application/json
    Content-Type: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    [
        {
            "url": "http://127.0.0.1:8000/api/alerts/e80e48a4e58b48ff9a1320a0aa0d68ab/",
            "uuid": "e80e48a4e58b48ff9a1320a0aa0d68ab",
            "alert_type": "first_alert",
            "message": "message#1",
            "severity": "Debug",
            "scope": "http://127.0.0.1:8000/api/instances/9d1d7e03b0d14fd0b42b5f649dfa3de5/",
            "created": "2015-05-29T14:24:27.342Z",
            "closed": null,
            "context": {
                'customer_abbreviation': 'customer_abbreviation',
                'customer_contact_details': 'customer details',
                'customer_name': 'Customer name',
                'customer_uuid': '53c6e86406e349faa7924f4c865b15ab',
                'quota_limit': '131072.0',
                'quota_name': 'ram',
                'quota_usage': '131071',
                'quota_uuid': 'f6ae2f7ca86f4e2f9bb64de1015a2815',
                'scope_name': 'DEV/logtest',
                'scope_uuid': '0238d71ee1934bd2839d4e71e5f9b91a'
            }
            "acknowledged": true,
        }
    ]


Create alert
------------

Run POST against */api/alerts/* to create or update alert. If alert with posted scope and alert_type already exists -
it will be updated. Only users with staff privileges can create alerts.

Request example:

.. code-block:: javascript

    POST /api/alerts/
    Accept: application/json
    Content-Type: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "scope": "http://testserver/api/projects/b9e8a102b5ff4469b9ac03253fae4b95/",
        "message": "message#1",
        "alert_type": "first_alert",
        "severity": "Debug"
    }


Close alert
-----------

To close alert - run POST against */api/alerts/<alert_uuid>/close/*. No data is required. Only users with staff
privileges can close alerts.


Acknowledge alert
-----------------

To acknowledge alert - run POST against */api/alerts/<alert_uuid>/acknowledge/*. No payload is required.
All users that can see alerts can also acknowledge it. If alert is already acknowledged endpoint will return error
with code 409(conflict).


Cancel alert acknowledgment
---------------------------

To cancel alert acknowledgment - run POST against */api/alerts/<alert_uuid>/cancel_acknowledgment/*.
No payload is required. All users that can see alerts can also cancel it acknowledgment. If alert is not acknowledged
endpoint will return error with code 409(conflict).


Statistics
----------

To get count of alerts per severities - run GET request against **/api/alerts/stats/**. This endpoint supports all
filters that are available for alerts list (/api/alerts/).

Response example:

.. code-block:: javascript

    {
        "debug": 2,
        "error": 1,
        "info": 1,
        "warning": 1
    }
