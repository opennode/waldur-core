Instance list
-------------

To get a list of instances, run GET against */api/instances/* as authenticated user. Note that a user can
only see connected instances:

- instances that belong to a project where a user has a role.
- instances that belong to a customer that a user owns.

Filtering of instance list is supported through HTTP query parameters, the following fields are supported:

- ?hostname=<hostname>
- ?customer_name=<customer name>
- ?state=<state symbol>
- ?project=<project_name>
- ?project_group=<project_group_name>
- ?template_name=<template name>

Sorting is supported in ascending and descending order by specifying a field to an **?o=** parameter.

- ?o=hostname - sort by hostname in ascending order
- ?o=state - sort by state in ascending order
- ?o=project__customer__name - sort by customer name in ascending order
- ?o=project__project_groups__name - sort by project group name
- ?o=project__name - sort by project name
- ?o=template__name - sort by template name


Instance permissions
--------------------

- Staff members can list all available VM instances in any cloud.
- Customer owners can list all VM instances in all the clouds that belong to any of the customers they own.
- Project administrators can list all VM instances, create new instances and start/stop/restart instances in all the clouds that are connected to any of the projects they are administrators in.
- Project managers can list all VM instances in all the clouds that are connected to any of the projects they are managers in.

Instance state
--------------

Each instance has a **state** field that defines its current operational state. Instance has a FSM that defines possible
state transitions. If a request is made to perform an operation on instance in incorrect state, a validation
error will be returned.

The UI can poll for updates to provide feedback after submitting one of the longer running operations.

In a DB, state is stored encoded with a symbol. States are:

- PROVISIONING_SCHEDULED = 'p'
- PROVISIONING = 'P'
- ONLINE = '+'
- OFFLINE = '-'
- STARTING_SCHEDULED = 'a'
- STARTING = 'A'
- STOPPING_SCHEDULED = 'o'
- STOPPING = 'O'
- ERRED = 'e'
- DELETION_SCHEDULED = 'd'
- DELETING = 'D'
- DELETED = 'x'
- RESIZING_SCHEDULED = 'r'
- RESIZING = 'R'

A graph of possible state transitions is shown below.

.. image:: ../images/instance-states.png

Create a new instance
---------------------

A new instance can be created by users with project administrator role or with staff privilege (is_staff=True).
To create a instance, client must define:

- hostname;
- description (optional);
- link to the template object;
- link to the flavor (it _must_ belong to a cloud, which is authorized for usage in the project);
- link to the project;
- link to user's public key (it must belong to a user, who will be able to log in to the instance);
- security_groups (optional).
- internal ips (optional);
- external ips (optional);

Example of a valid request:

.. code-block:: http

    POST /api/instances/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "hostname": "test VM",
        "description": "sample description",
        "template": "http://example.com/api/iaas-templates/1ee385bc043249498cfeb8c7e3e079f0/",
        "flavor": "http://example.com/api/flavors/c3c546b92845431188636d8f97df223c/",
        "project": "http://example.com/api/projects/661ee58978d9487c8ac26c56836585e0/",
        "ssh_public_key": "http://example.com/api/keys/6fbd6b24246f4fb38715c29bafa2e5e7/",
        "internal_ips": "10.242.22.8,172.18.216.75,192.168.162.2",
        "external ips": "131.107.140.29,216.21.127.62,210.143.155.57",
        "security_groups": [
            { "url": "http://example.com/api/security-groups/16c55dad9b3048db8dd60e89bd4d85bc/"},
            { "url": "http://example.com/api/security-groups/232da2ad9b3048db8dd60eeaa23d8123/"}
        ]
        },
    }

Stopping/starting an instance
-----------------------------

To stop/start an instance, run an authorized POST request against the instance UUID, appending the requested command.
Examples of URLs:

- POST /api/instances/6c9b01c251c24174a6691a1f894fae31/start/
- POST /api/instances/6c9b01c251c24174a6691a1f894fae31/stop/

Resizing an instance
--------------------

To resize an instance, submit a POST request to the instance's RPC url, specifying also UUID of a target flavor.
Example of a valid request:


.. code-block:: http

    POST /api/instances/6c9b01c251c24174a6691a1f894fae31/resize/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "flavor": "1ee385bc043249498cfeb8c7e3e079f0",
    }

To resize disk of the instance, submit a POST request to the instance's RPC url, specifying also size of the disk.
Example of a valid request:


.. code-block:: http

    POST /api/instances/6c9b01c251c24174a6691a1f894fae31/resize/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "disk_size": "1024",
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

- ?item=instance_usage_item(required. Have to be from list: 'cpu', 'memory', 'storage')
- ?from=timestamp(default: now - one hour, example: 1415910025)
- ?to=timestamp(default: now, example: 1415912625)
- ?datapoints=how many data points have to be in answer(default: 6)

Answer will be list of points(dictionaries) with fields: 'from', 'to', 'value'
