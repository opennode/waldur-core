Usage statistics
----------------
Warning! This endpoint is restricted to IAAS application.

Historical data of usage aggregated by projects/project_groups/customers.

URL: **/api/stats/usage/**

Available request parameters:

- ?aggregate=aggregate_model_name (default: 'customer'. Have to be from list: 'customer', 'project', 'project_group')
- ?uuid=uuid_of_aggregate_model_object (not required. If this parameter will be defined - result will contain only
  object with given uuid)
- ?item=instance_usage_item (required. Have to be from list: 'cpu', 'memory', 'storage').
  CPU is reported as utilisation and goes from 0 to 100% as reported by 'ps -o %cpu'. Memory and storage are in MiB.
- ?from=timestamp (default: now - one hour, example: 1415910025)
- ?to=timestamp (default: now, example: 1415912625)
- ?datapoints=how many data points have to be in answer(default: 6)

Answer will be list of dictionaries with fields:

- name - name of aggregate object (customer, project or project_group)
- datapoints - list of datapoints for aggregate object.
  Each datapoint is a dictionary with fields: 'from', 'to', 'value'. Datapoints are sorted in ascending time order.


Example:

.. code-block:: javascript

    [
        {
            "name": "Proj27",
            "datapoints": [
                {"to": 471970877, "from": 1, "value": 0},
                {"to": 943941753, "from": 471970877, "value": 0},
                {"to": 1415912629, "from": 943941753, "value": 3.0}
            ]
        },
        {
            "name": "Proj28",
            "datapoints": [
                {"to": 471970877, "from": 1, "value": 0},
                {"to": 943941753, "from": 471970877, "value": 0},
                {"to": 1415912629, "from": 943941753, "value": 3.0}
            ]
        }
    ]


Customer statistics
-------------------
Warning! This endpoint is restricted to IAAS application.

Summary of projects/groups/vms per customer.

URL: **/api/stats/customer/**

No input parameters. Answer will be list dictionaries with fields:

- name - customer name
- projects - count of customers projects
- project_groups - count of customers project groups
- instances - count of customers instances

Example:

.. code-block:: python

    [
        {"instances": 4, "project_groups": 1, "name": "Customer5", "projects": 2}
    ]


Resource statistics
-------------------
Warning! This endpoint is restricted to IAAS application.

Allocation of resources in a cloud backend.

URL: **/api/stats/resource/**

Required request GET parameter: *?auth_url* - cloud URL

Answer will be list dictionaries with fields:

**vCPUs:**

- vcpus_used - currently number of used vCPUs
- vcpu_quota - maximum number of vCPUs (from quotas)
- vcpus - maximum number of vCPUs (from hypervisors)

**Memory:**

- free_ram_mb - total available memory space on all physical hosts
- memory_mb_used - currently used memory size on all physical hosts
- memory_quota - maximum number of memory (from quotas)
- memory_mb - total size of memory for allocation

**Storage:**

- free_disk_gb - total available disk space on all physical hosts
- storage_quota - allocated storage quota


Example:

.. code-block:: javascript

    {
        "free_disk_gb": 14,
        "free_ram_mb": 510444,
        "memory_mb": 516588,
        "memory_mb_used": 6144,
        "memory_quota": 0,
        "storage_quota": 0,
        "vcpu_quota": 0,
        "vcpus": 64,
        "vcpus_used": 4
    }


Creation time statistics
------------------------

Historical information about creation time of projects, project groups and customers.

URL: **/api/stats/creation-time/**

Available request parameters:

- ?type=type_of_statistics_objects (required. Have to be from the list: 'customer', 'project', 'project_group')
- ?from=timestamp (default: now - 30 days, for example: 1415910025)
- ?to=timestamp (default: now, for example: 1415912625)
- ?datapoints=how many data points have to be in answer (default: 6)

Answer will be list of datapoints(dictionaries).
Each datapoint will contain fields: 'to', 'from', 'value'.
'Value' - count of objects, that were created between 'from' and 'to' dates.

Example:

.. code-block:: javascript

    [
        {"to": 471970877, "from": 1, "value": 5},
        {"to": 943941753, "from": 471970877, "value": 0},
        {"to": 1415912629, "from": 943941753, "value": 3}
    ]


Quotas statistics
-----------------

Quotas and quotas usage aggregated by projects/project_groups/customers.

URL: **/api/stats/quota/**

Available request parameters:

- ?aggregate=aggregate_model_name (default: 'customer'. Have to be from list: 'customer', 'project', 'project_group')
- ?uuid=uuid_of_aggregate_model_object (not required. If this parameter will be defined - result will contain only
  object with given uuid)
- ?quota_name - optional list of quota names, for example ram, vcpu, storage


Example result:

.. code-block:: javascript

    {
        "floating_ip_count": 150.0,
        "floating_ip_count_usage": 0.0,
        "instances": 300.0,
        "instances_usage": 2.0,
        "max_instances_usage": 1.0,
        "ram": 153600.0,
        "ram_usage": 5633.0,
        "security_group_count": 30.0,
        "security_group_count_usage": 13.0,
        "security_group_rule_count": 300.0,
        "security_group_rule_count_usage": 30.0,
        "storage": 3072000.0,
        "storage_usage": 82945.0,
        "vcpu": 300.0,
        "vcpu_usage": 3.0
    }


Quotas timeline statistics
--------------------------

Historical data of quotas and quotas usage aggregated by projects/project_groups/customers.

URL: **/api/stats/quota/timeline/**

Available request parameters:

- ?from=timestamp (default: now - 1 day, for example: 1415910025)
- ?to=timestamp (default: now, for example: 1415912625)
- ?interval (default: day. Has to be from list: hour, day, week, month)
- ?item=<quota_name>. If this parameter is not defined - endpoint will return data for all items.
- ?aggregate=aggregate_model_name (default: 'customer'. Have to be from list: 'customer', 'project', 'project_group')
- ?uuid=uuid_of_aggregate_model_object (not required. If this parameter is defined, result will contain only object with given uuid)

Answer will be list of dictionaries with fields, determining time frame. It's size is equal to interval parameter.
Values within each bucket are averaged for each project and then all projects metrics are summarized.

Value fields include:

- vcpu_limit - virtual CPUs quota
- vcpu_usage - virtual CPUs usage
- ram_limit - RAM quota limit, in MiB
- ram_usage - RAM usage, in MiB
- storage_limit - volume storage quota limit, in MiB
- storage_usage - volume storage quota consumption, in MiB

Example result:

.. code-block:: javascript

    [
        {
            "from": 1433880000,
            "to": 1433966400,
            "instances_limit": 13,
            "instances_usage": 1,
            "ram_limit": 54272,
            "ram_usage": 0,
            "storage_limit": 1054720,
            "storage_usage": 11264,
            "vcpu_limit": 23,
            "vcpu_usage": 1
        },
        {
            "from": 1433966400,
            "to": 1434052800,
            "instances_limit": 13,
            "instances_usage": 5,
            "ram_limit": 54272,
            "ram_usage": 1059,
            "storage_limit": 1054720,
            "storage_usage": 11264,
            "vcpu_limit": 23,
            "vcpu_usage": 5
        }
    ]


Alerts statistics
-----------------

Warning! This endpoint is *deprecated* use **/api/alerts/stats/** instead of it.

Health statistics based on the alert number and severity. You may also narrow down statistics by instances aggregated
by specific projects/project_groups/customers.

URL: **/api/stats/alert/**

All available request parameters are optional:

- ?from=timestamp
- ?to=timestamp
- ?aggregate=aggregate_model_name (default: 'customer'. Have to be from list: 'customer', 'project', 'project_group')
- ?uuid=uuid_of_aggregate_model_object (not required. If this parameter will be defined - result will contain only
  object with given uuid)
- ?opened - if this argument is in GET request - endpoint will return statistics only for alerts that are not closed
- ?alert_type=<alert_type> (can be list)
- ?scope=<url> concrete alert scope
- ?scope_type=<string> name of scope type (Ex.: instance, cloud_project_membership, project...)
- ?acknowledged=True|False - show only acknowledged (non-acknowledged) alerts
- ?created_from=<timestamp>
- ?created_to=<timestamp>
- ?closed_from=<timestamp>
- ?closed_to=<timestamp>


Answer will be dictionary where key is severity and value is a count of alerts.

Example:

.. code-block:: javascript

        {
            "Debug": 2,
            "Error": 1,
            "Info": 1,
            "Warning": 1
        }
