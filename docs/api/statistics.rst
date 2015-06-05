Usage statistics
----------------

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

Summary of projects/groups/vms per customer.

URL: /stats/customer/

No input parameters. Answer will be list dictionaries with fields:

- name - customer name
- projects - count of customers projects
- project_groups - count of customers project groups
- instances - count of customers instances

Example:

.. code-block:: python

    [
        {'instances': 4, 'project_groups': 1, 'name': 'Customer5', 'projects': 2}
    ]


Resource statistics
-------------------

Allocation of resources in a cloud backend.

URL: **/stats/resource/**

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

Answer will be dictionary with fields:

- vcpu - virtual CPUs quota
- ram - max RAM size in MiB
- storage - max storage size in MiB
- max_instances - max number of running instance
- vcpu_usage - virtual CPUs usage
- ram_usage - RAM usage
- storage_usage - storage usage in MiB
- max_instances_usage - number of running instance


Example result:

.. code-block:: javascript

    {
        'vcpu': 2,
        'ram': 4096,
        'storage': 16384,
        'max_instances': 4,
        'vcpu_usage': 1,
        'ram_usage': 4096,
        'storage_usage': 16000,
        'max_instances_usage': 3
    }


Alerts statistics
------------------------

Health statistics based on the alert number and severity. You may also narrow down statistics by instances aggregated by specific projects/project_groups/customers.

URL: **/api/stats/alert/**

All available request parameters are optional:

- ?from=timestamp (default: now - 1 day, for example: 1415910025)
- ?to=timestamp (default: now, for example: 1415912625)
- ?aggregate=aggregate_model_name (default: 'customer'. Have to be from list: 'customer', 'project', 'project_group')
- ?uuid=uuid_of_aggregate_model_object (not required. If this parameter will be defined - result will contain only object with given uuid)

Answer will be dictionary where key is severity and value is a count of alerts.

Example:

.. code-block:: javascript

        {
            "Debug": 2,
            "Error": 1,
            "Info": 1,
            "Warning": 1
        }
