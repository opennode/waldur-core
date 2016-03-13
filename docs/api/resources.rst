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

Also it is possible to filter and order by resource-specific fields, but this filters will be applied only to
resources that support such filtering. For example it is possible to sort resource by ?o=ram, but sugarcrm crms
will ignore this ordering, because they do not support such option.


SLA values
^^^^^^^^^^

Resources may have SLA attached to it. Example rendering of SLA:

.. code-block:: javascript

    "sla": {
        "value": 95.0
        "agreed_value": 99.0,
        "period": "2016-03"
    }

You may filter or order resources by SLA. Default period is current year and month.

- Example query for filtering list of resources by actual SLA:

  /api/<resource_endpoint>/?actual_sla=90&period=2016-02

- Warning! If resource does not have SLA attached to it, it is not included in ordered response.
  Example query for ordering list of resources by actual SLA:

  /api/<resource_endpoint>/?o=actual_sla&period=2016-02

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
*/api/resource-sla-state-transition/*.

Supported query arguments:

- ?scope=<URL of resource>
- ?period - use the format defined above.

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

Monitoring items
^^^^^^^^^^^^^^^^

Resources may have monitoring items attached to it. Example rendering of monitoring items:

.. code-block:: javascript

    "monitoring_items": {
       "application_state": 1
    }

You may filter or order resources by monitoring item.

- Example query for filtering list of resources by installation state:

  /api/<resource_endpoint>/?monitoring__installation_state=1

- Warning! If resource does not have monitoring item attached to it, it is not included in ordered response.
  Example query for ordering list of resources by installation state:

  /api/<resource_endpoint>/?o=monitoring__installation_state


Tags
^^^^

Resource may have tags attached to it. Example of tags rendering:

.. code-block:: javascript

    "tags": [
        "license-os:centos7",
        "os-family:linux",
        "license-application:postgresql",
        "support:premium"
    ]

Tags filtering:

 - ?tag=IaaS - filter by full tag name. Can be list.
 - ?tag__license-os=centos7 - filter by tags with particular prefix.

Tags ordering:

 - ?o=tag__license-os - order by tag with particular prefix. Instances without given tag will not be returned.


Resource actions
----------------

To get a list of supported resources' actions, run OPTIONS against **/api/<resource_url>/** as an authenticated user.

Example rendering of response:

.. code-block:: javascript

    {
        "actions": {
            "destroy": {
                "destructive": true,
                "type": "button",
                "method": "DELETE",
                "title": "Destroy"
            },
            "resize": {
                "fields": {
                    "flavor": {
                        "type": "select_url",
                        "required": false,
                        "url": "http://example.com/api/openstack-flavors/"
                    },
                    "disk_size": {
                        "type": "integer",
                        "required": false,
                        "label": "Disk size",
                        "min_value": 1
                    }
                },
                "destructive": false,
                "type": "form",
                "method": "POST",
                "title": "Resize virtual machine"
            },
            "restart": {
                "destructive": false,
                "type": "button",
                "method": "POST",
                "title": "Restart"
            },
            "start": {
                "destructive": false,
                "type": "button",
                "method": "POST",
                "title": "Start"
            },
            "stop": {
                "destructive": false,
                "type": "button",
                "method": "POST",
                "title": "Stop"
            },
            "unlink": {
                "destructive": true,
                "type": "button",
                "method": "POST",
                "title": "Unlink"
            },
            "PUT": {
                "name": {
                    "type": "string",
                    "required": true,
                    "label": "Name",
                    "max_length": 150
                },
                "description": {
                    "type": "string",
                    "required": false,
                    "label": "Description",
                    "max_length": 500
                },
                "security_groups": {
                    "type": "field",
                    "required": false,
                    "label": "Security groups",
                    "many": true
                }
            }
        }
    }

OpenStack resources list
------------------------

Deprecated. Use filtering by SLA against **api/resources** endpoint.
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

