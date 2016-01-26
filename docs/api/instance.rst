Instance list
-------------

To get a list of instances, run GET against **/api/instances/** as authenticated user. Note that a user can
only see connected instances:

- instances that belong to a project where a user has a role.
- instances that belong to a customer that a user owns.

Filtering of instance list is supported through HTTP query parameters, the following fields are supported:

- ?hostname=<hostname> **deprecated**, use ?name=<name> instead
- ?customer=<customer uuid>
- ?customer_name=<customer name>
- ?customer_native_name=<customer native name>
- ?customer_abbreviation=<customer abbreviation>
- ?state=<state symbol>
- ?project=<project uuid>
- ?project=<project name>
- ?project_group=<project group uuid>
- ?project_group=<project group name>
- ?template_name=<template name>
- ?description=<description>
- ?cores=<number of cores>
- ?ram=<size of ram in MiB>
- ?created=<time of creation>
- ?system_volume_size=<size of system disk in MiB>
- ?data_volume_size=<size of data disk in MiB>
- ?type=<type of the resource: IaaS or PaaS>
- ?backend_id=<openstack id of instance>
- ?installation_state=<instance installation state (FAIL, NO DATA, NOT OK, OK)>

Sorting is supported in ascending and descending order by specifying a field to an **?o=** parameter.

- ?o=hostname **deprecated**, use ?o=name instead - sort by name (deprecated: ?o=hostname)
- ?o=state - sort by state
- ?o=customer_name - sort by customer name
- ?o=customer_native_name - sort by customer native name
- ?o=customer_abbreviation - sort by customer abbreviation
- ?o=project_group_name - sort by project group name
- ?o=project_name - sort by project name
- ?o=template_name - sort by template name
- ?o=project__customer__name - **deprecated**, use ?o=customer_name instead
- ?o=project__project_groups__name - **deprecated**, use ?o=project_group_name instead
- ?o=cores - sort by number of cores
- ?o=ram - sort by size of ram
- ?o=system_volume_size - sort by system volume size
- ?o=data_volume_size - sort by data volume size
- ?o=created - sort by creation time
- ?o=type - sort by resource type
- ?o=installation_state - sort by instance installation_state
- ?o=project__name - **deprecated**, use ?o=project_name instead
- ?o=template__name - **deprecated**, use ?o=template_name instead

Sorting can be done by the following fields, specifying field name as a parameter to **?o=<field_name>**. To get a
descending sorting prefix field name with a **-**.

Instance permissions
--------------------

- Staff members can list all available VM instances in any cloud.
- Customer owners can list all VM instances in all the clouds that belong to any of the customers they own.
- Project administrators can list all VM instances, create new instances and start/stop/restart instances in all the
  clouds that are connected to any of the projects they are administrators in.
- Project managers can list all VM instances in all the clouds that are connected to any of the projects they are
  managers in.

Instance state
--------------

Each instance has a **state** field that defines its current operational state. Instance has a FSM that defines possible
state transitions. If a request is made to perform an operation on instance in incorrect state, a validation
error will be returned.

The UI can poll for updates to provide feedback after submitting one of the longer running operations.

In a DB, state is stored encoded with a symbol. States are:

- PROVISIONING_SCHEDULED = 1
- PROVISIONING = 2
- ONLINE = 3
- OFFLINE = 4
- STARTING_SCHEDULED = 5
- STARTING = 6
- STOPPING_SCHEDULED = 7
- STOPPING = 8
- ERRED = 9
- DELETION_SCHEDULED = 10
- DELETING = 11
- RESIZING_SCHEDULED = 13
- RESIZING = 14
- RESTARTING_SCHEDULED = 15
- RESTARTING = 16

Any modification of an instance in unstable or PROVISIONING_SCHEDULED state is prohibited
and will fail with 409 response code. Assuming stable states are ONLINE and OFFLINE.

A graph of possible state transitions is shown below.

.. image:: ../images/instance-states.png

Instance installation state
---------------------------

Each PaaS instance has a **installation state** field that defines its current installation state.

Possible states:

- OK - installation succeeded
- NOT OK - installation is not ready yet
- NO DATA - no information about installation state
- FAIL - installation failed


Create a new instance
---------------------

A new instance can be created by users with project administrator role or with staff privilege (is_staff=True).
PaaS instance can be created only if cloud_project_membership that connects its project and flavor
have external_network_id.
To create a instance, client must define:

- hostname **deprecated**, use name instead;
- description (optional);
- link to the template object (it *must* be connected to a cloud, which is authorized for usage in the project);
- link to the flavor (it *must* belong to a cloud, which is authorized for usage in the project);
- link to the project;
- link to user's public key (user owning this key will be able to log in to the instance);
- external_ips (optional, each ip address *must* be from the list of :doc:`floating ips <floating_ips>`);
- security_groups (optional);
- system_volume_size in MiB (optional);
- data_volume_size in MiB (optional, sum of instance's system_volume_size and data_volume_size has to be lower
  than available storage quota);
- user_data (optional) - YAML field with user commands for created instance;

Example of a valid request:

.. code-block:: http

    POST /api/instances/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "name": "test VM",
        "description": "sample description",
        "template": "http://example.com/api/iaas-templates/1ee385bc043249498cfeb8c7e3e079f0/",
        "flavor": "http://example.com/api/flavors/c3c546b92845431188636d8f97df223c/",
        "project": "http://example.com/api/projects/661ee58978d9487c8ac26c56836585e0/",
        "ssh_public_key": "http://example.com/api/keys/6fbd6b24246f4fb38715c29bafa2e5e7/",
        "external_ips": [
            "131.107.140.29",
            "216.21.127.62",
            "210.143.155.57"
        ],
        "security_groups": [
            { "url": "http://example.com/api/security-groups/16c55dad9b3048db8dd60e89bd4d85bc/"},
            { "url": "http://example.com/api/security-groups/232da2ad9b3048db8dd60eeaa23d8123/"}
        ]
    }

Instance display
----------------

Example rendering of the Instance object:

.. code-block:: javascript

    [
        {
            "url": "http://example.com/api/instances/20602b6283c446ad9420b3230bb83dc5/",
            "uuid": "20602b6283c446ad9420b3230bb83dc5",
            "name": "host 123",
            "description": "My instance",
            "start_time": "2014-12-15T05:54:38.605Z",
            "template": "http://localhost:8000/api/iaas-templates/0e2d11a10e3441c79152d77ba023c144/",
            "template_name": "CentOS 6 x64 MbALe",
            "template_os": "CentOS 6.5",
            "cloud": "http://localhost:8000/api/clouds/bd6d04242191466f9b846bff44e39acd/",
            "cloud_name": "CloudAccount of Customer fGSu (FnUHVdBTwTnkm  qJ)",
            "cloud_uuid": "bd6d04242191466f9b846bff44e39acd",
            "project": "http://localhost:8000/api/projects/8c4c2f2434c744cfb02a787f102abae0/",
            "project_name": "Project CMyA",
            "project_uuid": "8c4c2f2434c744cfb02a787f102abae0",
            "customer": "http://localhost:8000/api/customers/ea5f18624b3346fa8290dac3ef032085/",
            "customer_name": "Customer fGSu",
            "customer_abbreviation": "MYpzQXOr",
            "key_name": "public key X",
            "key_fingerprint": "74:1c:72:cc:07:66:9e:17:cb:84:63:70:c2:e7:89:ec",
            "project_groups": [
                {
                    "url": "http://localhost:8000/api/project-groups/b04f53e72e9b46949fa7c3a0ef52cd91/",
                    "name": "Project Group iEtUsyy",
                    "uuid": "b04f53e72e9b46949fa7c3a0ef52cd91"
                }
            ],
            "security_groups": [
                {
                    "url": "http://localhost:8000/api/security-groups/de1ef971bcd747c7aee1e451b31255c9/",
                    "name": "http",
                    "rules": [
                        {
                            "protocol": "tcp",
                            "from_port": 80,
                            "to_port": 80,
                            "cidr": "0.0.0.0/0"
                        }
                    ],
                    "description": "Security group for web servers"
                }
            ],
            "external_ips": [
                "119.177.90.33",
                "187.92.54.148",
                "33.64.131.221"
            ],
            "internal_ips": [
                "10.93.209.252",
                "10.89.138.41",
                "10.178.2.220"
            ],
            "state": "Provisioning Scheduled",
            "backups": [],
            "backup_schedules": [],
            "instance_licenses": [
                {
                    "uuid": "9cda1ecd43004abf8fa398a944fec32d",
                    "name": "Redhat 6 license",
                    "license_type": "RHEL6",
                    "service_type": "IaaS"
                },
                {
                    "uuid": "1fcb186b65f7430fb1a3d558d97d1630",
                    "name": "Windows server license",
                    "license_type": "Windows 2012 Server",
                    "service_type": "IaaS"
                }
            ],
            "agreed_sla": "99.999",
            "system_volume_size": 46080,
            "data_volume_size": 20480,
            "cores": 2,
            "ram": 1024,
            "created": "2015-01-26T14:06:00.978Z",
            "backend_id": "9c4dacb2-34f4-4da5-ac83-ba7f12ba19f1"
        }
    ]

Stopping/starting/restarting an instance
-----------------------------------------

To stop/start/restart an instance, run an authorized POST request against the instance UUID,
appending the requested command.
Examples of URLs:

- POST /api/instances/6c9b01c251c24174a6691a1f894fae31/start/
- POST /api/instances/6c9b01c251c24174a6691a1f894fae31/stop/
- POST /api/instances/6c9b01c251c24174a6691a1f894fae31/restart/

If instance is in the state that does not allow this transition, error code will be returned.

Resizing an instance
--------------------

To resize an instance, submit a POST request to the instance's RPC URL, specifying URI of a target flavor.
Example of a valid request:


.. code-block:: http

    POST /api/instances/6c9b01c251c24174a6691a1f894fae31/resize/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "flavor": "http://example.com/api/flavors/1ee385bc043249498cfeb8c7e3e079f0/"
    }

To resize data disk of the instance, submit a POST request to the instance's RPC URL, specifying size of the disk.
Additional size of instance cannot be over the storage quota.

Example of a valid request:


.. code-block:: http

    POST /api/instances/6c9b01c251c24174a6691a1f894fae31/resize/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "disk_size": 1024
    }

Deletion of an instance
-----------------------

Deletion of an instance is done through sending a DELETE request to the instance URI.
Valid request example (token is user specific):

.. code-block:: http

    DELETE /api/instances/6c9b01c251c24174a6691a1f894fae31/ HTTP/1.1
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

NB! Only stopped instances can be deleted.


Instance usage info
-------------------

To get information about instance usage, make GET request to /api/instances/<uuid>/usage/ with such parameters:

- ?item=instance_usage_item(required. Have to be from list: 'cpu', 'cpu_util', 'memory', 'memory_util', 'storage', 'storage_root_util', 'storage_data_util')
- ?from=timestamp(default: now - one hour, example: 1415910025)
- ?to=timestamp(default: now, example: 1415912625)
- ?datapoints=how many data points have to be in answer(default: 6)

Answer will be list of points(dictionaries) with fields: 'from', 'to', 'value'

Instance calculated usage statistics
------------------------------------

To get max or min utilization of cpu, memory and storage of the instance within timeframe, make GET request to
/api/instances/<uuid>/calculated_usage/ with optional parameters:

- ?from=timestamp (default: now - one hour, example: 1415910025)
- ?to=timestamp (default: now, example: 1415912625)
- ?item=<item_name> (Available options: 'cpu_util', 'memory_util', 'storage_root_util', 'storage_data_util'.
        Can be list. Default: all available options)
- ?method=<calculate_method> (Available options: 'MAX', 'MIN'. Default: 'MAX')

Answer is list of dictionaries with fields item, value and timestamp, where item is one of:

- cpu_util - CPU usage in percents
- memory_util - memory usage in percents
- storage_root_util - root storage usage in percents
- storage_data_util - data storage usage in percents

.. code-block:: javascript

    [
        {
            "item": "cpu_util",
            "value": 0,
            "timestamp": 1435491012
        },
        {
            "item": "storage_root_util",
            "value": 92,
            "timestamp": 1435491518
        },
        {
            "item": "storage_data_util",
            "value": 99,
            "timestamp": 1435491518
        },
        {
            "item": "memory_util",
            "value": 32,
            "timestamp": 1435491159
        }
    ]

Assigning floating IP to the instance
-------------------------------------

To assign floating IP to the instance, make POST request to
**/api/instances/<uuid>/assign_floating_ip/** with floating IP UUID parameter. Note that instance should be in stable state,
cloud project membership of the instance should be in stable state and have external network.

Example of a valid request:

.. code-block:: http

    POST /api/instances/6c9b01c251c24174a6691a1f894fae31/assign_floating_ip/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "floating_ip_uuid": "1fcb186b65f7430fb1a3d558d97d1630"
    }

