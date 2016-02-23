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

URL: **/api/stats/aggregated/**

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
