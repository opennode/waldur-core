Usage statistics
----------------

Historical data of usage aggregated by projects/project_groups/customers.

URL: /stats/usage/

Available request parameters:

- ?aggregate=aggregate_model_name(default: 'customer'. Have to be from list: 'customer', 'project', 'project_group')
- ?uuid=uuid_of_aggregate_model_object(not required. If this parameter will be defined - result will contain only object with given uuid)
- ?item=instance_usage_item(required. Have to be from list: 'cpu', 'memory', 'storage')
- ?from=timestamp(default: now - one hour, example: 1415910025)
- ?to=timestamp(default: now, example: 1415912625)
- ?datapoints=how many data points have to be in answer(default: 6)

Answer will be list of dictionaries with fields:

- name - name of aggregate object (customer, project or project_group)
- datapoints - list of datapoints for aggregate object. Each datapoint is a dictionary with fields: 'from', 'to', 'value'


Example:

.. code-block:: javascript

    [
        {
            'name': 'Proj27',
            'datapoints': [
                {'to': 471970877L, 'from': 1L, 'value': 0},
                {'to': 943941753L, 'from': 471970877L, 'value': 0},
                {'to': 1415912629L, 'from': 943941753L, 'value': 3.0}
            ]
        },
        {
            'name': 'Proj28',
            'datapoints': [
                {'to': 471970877L, 'from': 1L, 'value': 0},
                {'to': 943941753L, 'from': 471970877L, 'value': 0},
                {'to': 1415912629L, 'from': 943941753L, 'value': 3.0}
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

Allocation of resources in G-Cloud.

URL: /stats/resource/

Required request GET parameter: ?auth_url - cloud URL

Answer will be list dictionaries with fields:

- count - number of physical hosts (hypervisors)
- current_workload
- disk_available_least
- free_disk_gb - total available disk space on all physical hosts
- free_ram_mb - total available memory space on all physical hosts
- local_gb
- local_gb_used
- memory_mb - total size of memory for allocation
- memory_mb_used - currently used memory size
- memory_quota - maximum number of memory (from quotas)
- running_vms - total number of running VMs
- storage_quota - allocated storaeg quota
- vcpu_quota - maximum number of vCPUs (from quotas)
- vcpus - maximum number of vCPUs (from hypervisors)
- vcpus_used - currently number of used vCPUs

The exact semantics of the remaining fields are left as a puzzle to the reader.

Example:

.. code-block:: javascript

    {
        "count": 2,
        "current_workload": 0,
        "disk_available_least": 48,
        "free_disk_gb": 14,
        "free_ram_mb": 510444,
        "local_gb": 56,
        "local_gb_used": 42,
        "memory_mb": 516588,
        "memory_mb_used": 6144,
        "memory_quota": 0,
        "running_vms": 4,
        "storage_quota": 0,
        "vcpu_quota": 0,
        "vcpus": 64,
        "vcpus_used": 4
    }


Creation time statistics
------------------------

Historical information about creation time of projects, project groups and customers.

URL: /stats/creation-time/

Available request parameters:

- ?type=type_of_statistics_objects(required. Have to be from list: 'customer', 'project', 'project_group')
- ?from=timestamp(default: now - 30 days, example: 1415910025)
- ?to=timestamp(default: now, example: 1415912625)
- ?datapoints=how many data points have to be in answer(default: 6)

Answer will be list of datapoints(dictionaries).
Each datapoint will contain fields: 'to', 'from', 'value'.
'Value' - count of objects, that were created between 'from' and 'to' dates.

Example:

.. code-block:: javascript

    [
        {'to': 471970877L, 'from': 1L, 'value': 5},
        {'to': 943941753L, 'from': 471970877L, 'value': 0},
        {'to': 1415912629L, 'from': 943941753L, 'value': 3}
    ]


