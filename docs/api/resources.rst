Resources list
--------------

Use */api/resources/* to get a list of all the resources of any type that a user can see.

Supported filters are:

- ?name - case insensitive matching of a resource name
- ?resource_type (can be list) - for example, DigitalOcean.Droplet, GitLab.Project
- ?state=<resource state>. Possible values: Provisioning Scheduled, Provisioning, Online, Offline, Starting Scheduled,
                           Starting, Stopping Scheduled, Stopping, Erred, Deletion Scheduled, Deleting,
                           Resizing Scheduled, Resizing, Restarting Scheduled, Restarting
- ?uuid - exact math of a resource UUID
- ?description=<resource description>
- ?customer=<customer uuid> (deprecated, please use customer_uuid instead)
- ?customer_uuid=<customer uuid>
- ?customer_name=<customer name>
- ?customer_native_name=<customer native name>
- ?customer_abbreviation=<customer abbreviation>
- ?project=<project uuid> (deprecated, please use project_uuid instead)
- ?project_uuid=<project uuid>
- ?project_name=<project_name>
- ?project_group=<project_group uuid> (deprecated, please use project_group_uuid instead)
- ?project_group_uuid=<project_group uuid>
- ?project_group_name=<project_group name>
- ?service_uuid=<service uuid>
- ?service_name=<service name>

Supported ordering:

- ?o=name
- ?o=state
- ?o=customer_name
- ?o=customer_native_name
- ?o=customer_abbreviation
- ?o=created
- ?o=project_name
- ?o=project_group_name

Also it is possible to filter and order by resource-specific fields, but this filters will be applied only for to
resources that support such filtering. For example it is possible to filter resource by ?o=ram, but sugarcrm crms
will ignore this ordering, because they do not support such option.


OpenStack resources list
------------------------

Use */api/iaas-resources/* to get a list of all the resources that a user can see.
Only resources that have agreed and actual SLA values are shown.

Supported filters are:

- ?hostname **deprecated**, use ?name instead; - case insensitive matching of a name
- ?service_name - case insensitive matching of a service name
- ?customer_name - case insensitive matching of a customer name
- ?customer_native_name - case insensitive matching of a customer native name
- ?customer_abbreviation - case insensitive matching of a customer abbreviation
- ?project_name - case insensitive matching of a project name
- ?project_group_name - case insensitive matching of a project_group name
- ?agreed_sla - exact match of SLA numbers
- ?actual_sla - exact match of SLA numbers
- ?project_groups -  **deprecated**, use ?project_group_name instead

Ordering can be done by the following fields (prefix with **-** for descending order):

- ?o=hostname **deprecated**, use ?o=name instead;
- ?o=template_name
- ?o=customer_name
- ?o=customer_abbreviation
- ?o=customer_native_name
- ?o=project_name
- ?o=project_group_name
- ?o=agreed_sla
- ?o=actual_sla
- ?o=template__name - **deprecated**, use ?o=template_name instead
- ?o=project__customer__name - **deprecated**, use ?o=customer_name instead
- ?o=project__name - **deprecated**, use ?o=project_name instead
- ?o=project__project_groups__name - **deprecated**, use ?o=project_group_name instead
- ?o=slas__value - **deprecated**, use ?o=actual_sla instead

Response example:

.. code-block:: http

    GET /api/iaas-resources/ HTTP/1.1

    HTTP/1.0 200 OK
    Content-Type: application/json
    Vary: Accept
    Allow: GET, HEAD, OPTIONS
    X-Result-Count: 1

    [
        {
            "url": "http://example.com/api/iaas-resources/0356addb8e9742e7b984ebcaf5912c6b/",
            "uuid": "0356addb8e9742e7b984ebcaf5912c6b",
            "state": "Offline",
            "name": "FromBackup777",
            "template_name": "cirros-0.3.1-x86_64",
            "customer_name": "Customer A",
            "customer_native_name": "Customer A (native)",
            "customer_abbreviation": "CA",
            "project_name": "STG/Backups",
            "project_uuid": "19e4581367cb4f93bf77c21f68fbc2d1",
            "project_url": "http://example.com/api/projects/19e4581367cb4f93bf77c21f68fbc2d1/",
            "project_groups": [],
            "agreed_sla": "95",
            "actual_sla": null,
            "service_type": "IaaS",
            "access_information": []
        }
    ]


SLA periods
^^^^^^^^^^^

Service list is displaying current SLAs for each of the items. By default, SLA period is set to the current month. To
change the period pass it as a query argument:

- ?period=YYYY-MM - return a list with SLAs for a given month
- ?period=YYYY - return a list with SLAs for a given year

In all cases all currently running resources are returned, if SLA for the given period is not known or not present, it
will be shown as **null** in the response.

SLA events
^^^^^^^^^^

Service SLAs are connected with occurrences of events. To get a list of such events issue a GET request to
*/resources/<service_uuid>/events/*. Optionally period can be supplied using the format defined above.

The output contains a list of states and timestamps when the state was reached. The list is sorted in descending order
by the timestamp.

Example output:

.. code-block:: javascript

    [
        {
            "timestamp": 1418043540,
            "state": "U"
        },
        {
            "timestamp": 1417928550,
            "state": "D"
        },
        {
            "timestamp": 1417928490,
            "state": "U"
        }
    ]
