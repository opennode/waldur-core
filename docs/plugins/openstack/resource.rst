Resource
========

OpenStack instance permissions
------------------------------

- Staff members can list all available VM instances in any service.
- Customer owners can list all VM instances in all the services that belong to any of the customers they own.
- Project administrators can list all VM instances, create new instances and start/stop/restart instances in all the
  services that are connected to any of the projects they are administrators in.
- Project managers can list all VM instances in all the services that are connected to any of the projects they are
  managers in.

OpenStack instance states
-------------------------

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

.. image:: /images/instance-states.png

List OpenStack instances
------------------------

To get a list of instances, run GET against **/api/openstack-resources/** as authenticated user. Note that a user can
only see connected instances:

- instances that belong to a project where a user has a role.
- instances that belong to a customer that a user owns.

Filtering of instance list is supported through HTTP query parameters, the following fields are supported:

- ?name=<name>
- ?customer=<customer uuid>
- ?customer_name=<customer name>
- ?customer_native_name=<customer native name>
- ?customer_abbreviation=<customer abbreviation>
- ?state=<state symbol>
- ?project=<project uuid>
- ?project_name=<project name>
- ?project_group=<project group uuid>
- ?project_group_name=<project group name>
- ?description=<description>
- ?cores=<number of cores>
- ?ram=<size of ram in MiB>
- ?created=<time of creation>
- ?system_volume_size=<size of system disk in MiB>
- ?data_volume_size=<size of data disk in MiB>

Sorting is supported in ascending and descending order by specifying a field to an **?o=** parameter.

- ?o=name - sort by name
- ?o=state - sort by state
- ?o=customer_name - sort by customer name
- ?o=customer_native_name - sort by customer native name
- ?o=customer_abbreviation - sort by customer abbreviation
- ?o=project_group_name - sort by project group name
- ?o=project_name - sort by project name
- ?o=project__name - **deprecated**, use ?o=project_name instead
- ?o=project__customer__name - **deprecated**, use ?o=customer_name instead
- ?o=project__project_groups__name - **deprecated**, use ?o=project_group_name instead
- ?o=cores - sort by number of cores
- ?o=ram - sort by size of ram
- ?o=system_volume_size - sort by system volume size
- ?o=data_volume_size - sort by data volume size
- ?o=created - sort by creation time

Sorting can be done by the following fields, specifying field name as a parameter to **?o=<field_name>**. To get a
descending sorting prefix field name with a **-**.

Create OpenStack instance
-------------------------

A new instance can be created by users with project administrator role or with staff privilege (is_staff=True).
To create a instance, client must define:

- name
- description (optional);
- service project link (connection between project and OpenStack service);
- link to the flavor (it *must* belong to a service, which is authorized for usage in the project);
- link to the image (it *must* belong to a service, which is authorized for usage in the project);
- link to user's public key (user owning this key will be able to log in to the instance);
- skip_external_ip_assignment (should be true, if user do not want to assign floating IP);
- security_groups (optional);
- system_volume_size (in MiB);
- data_volume_size (in MiB, sum of instance's system_volume_size and data_volume_size has to be lower
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
        "image": "http://example.com/api/openstack-images/1ee380602b6283c446ad9420b3230bf0/",
        "flavor": "http://example.com/api/openstack-flavors/1ee385bc043249498cfeb8c7e3e079f0/",
        "ssh_public_key": "http://example.com/api/keys/6fbd6b24246f4fb38715c29bafa2e5e7/",
        "service_project_link": "http://example.com/api/openstack-service-project-link/674/".
        "data_volume_size": 1024,
        "system_volume_size": 20480,
        "security_groups": [
            { "url": "http://example.com/api/security-groups/16c55dad9b3048db8dd60e89bd4d85bc/"},
            { "url": "http://example.com/api/security-groups/232da2ad9b3048db8dd60eeaa23d8123/"}
        ]
    }

Display OpenStack instance
--------------------------

Example rendering of the Instance object:

.. code-block:: javascript

    [
        {
            "url": "http://example.com/api/openstack-instances/abceed63b8e844afacd63daeac855474/",
            "uuid": "abceed63b8e844afacd63daeac855474",
            "name": "wordpress",
            "description": "",
            "start_time": "2015-10-15T14:38:04Z",
            "service": "http://example.com/api/openstack/2c41511fc27b4f32b1255c2755e7926a/",
            "service_name": "Stratus",
            "service_uuid": "2c41511fc27b4f32b1255c2755e7926a",
            "project": "http://example.com/api/projects/5e7d93955f114d88981dea4f32ab673d/",
            "project_name": "visual-studio",
            "project_uuid": "5e7d93955f114d88981dea4f32ab673d",
            "customer": "http://example.com/api/customers/00576c9790fa4d60bb58d6a557090932/",
            "customer_name": "College of Technical Subjects",
            "customer_native_name": "",
            "customer_abbreviation": "",
            "project_groups": [],
            "resource_type": "OpenStack.Instance",
            "state": "Online",
            "created": "2015-10-15T14:33:54Z",
            "cores": 1,
            "ram": 2048,
            "disk": 21504,
            "external_ips": [
                "49.255.68.119"
            ],
            "internal_ips": [
                "192.168.42.11"
            ],
            "system_volume_size": 20480,
            "data_volume_size": 1024,
            "security_groups": []
        },
    ]


Import OpenStack instance
-------------------------

To get a list of OpenStack instances available for import, run GET against **/openstack/<service_uuid>/link/** as
an authenticated user.

**project_uuid** parameter should be supplied.

Example of a valid request:

.. code-block:: http

    GET /api/openstack/08039f01c9794efc912f1689f4530cf0/link/?project_uuid=e5f973af2eb14d2d8c38d62bcbaccb33 HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    [
        {
            "id": "65207eb8-7fff-4ddc-9a70-9c6f280646c3",
            "name": "my-test"
            "status": "SHUTOFF",
            "created_at": "2015-06-11T10:30:43Z",
        },
        {
            "id": "bd5ec24d-9164-440b-a9f2-1b3c807c5df3",
            "name": "some-gbox"
            "status": "ACTIVE",
            "created_at": "2015-04-29T09:51:07Z",
        }
    ]

To import (link with NodeConductor) instance issue POST against the same endpoint with instance backend id.

Example of a request:

.. code-block:: http

    POST /api/openstack/08039f01c9794efc912f1689f4530cf0/link/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "backend_id": "bd5ec24d-9164-440b-a9f2-1b3c807c5df3",
        "project": "http://example.com/api/projects/e5f973af2eb14d2d8c38d62bcbaccb33/"
    }
