Usage statistics
----------------

Historical data of usage aggregated by projects/project_groups/customers.

URL: /stats/usage/

Available request parameters:

- ?aggregate=aggregate_model_name(default: 'customer'. Have to be from list: 'customer', 'project', 'project_group')
- ?item=instance_usage_item(required. Have to be from list: 'cpu', 'memory', 'storage')
- ?from=timestamp(default: now - one hour, example: 1415910025)
- ?to=timestamp(default: now, example: 1415912625)
- ?datapoints=how many data points have to be in answer(default: 6)

Answer will be list of dictionaries with fields:

- name - name of aggregate object (customer, project or project_group)
- datapoints - list of datapoints for aggregate object. Each datapoint is a dictionary with fields: 'from', 'to', 'value'



Example:

.. code-block:: python

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
'ram_quota', 'vcpu_quota', 'storage_quota', 'free_disk_gb', 'disk_available_least', 'local_gb', 'free_ram_mb', 'memory_mb_used', 'count', 'vcpus_used', 'local_gb_used', u'memory_mb', 'current_workload', 'vcpus', 'running_vms'


Example:

.. code-block:: python

    {
        'ram_quota': 7.0,
        'vcpu_quota': 7,
        'free_disk_gb': 12,
        'disk_available_least': 6,
        'local_gb': 12,
        'free_ram_mb': 6636,
        'memory_mb_used': 1024,
        'count': 2,
        'vcpus_used': 0,
        'storage_quota': 79.395059159317753,
        'local_gb_used': 0,
        'memory_mb': 7660,
        'current_workload': 0,
        'vcpus': 2,
        'running_vms': 0
    }
