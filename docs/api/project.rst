Project list
------------

To get a list of projects, run GET against */api/projects/* as authenticated user. Note that a user can
only see connected projects:

- projects that the user owns as a customer
- projects where user has any role

Supported logic filters:

- ?can_manage - return a list of projects where current user is manager, group manager or a customer owner;
- ?can_admin - return a list of projects where current user is admin.

Field filters:

- ?customer=<Customer UUID> - return a list of projects belonging to a specific customer.
- ?project_group=<Project Group UUID> - return a list of projects in a specified project group.
- ?project_group_name=<Project group name> - return a list of projects with belonging to groups with matching names
- ?description=<text> - return a list of projects with description matching a given text
- ?vcpu=<number> - return a list of projects with a specified vcpu quota
- ?ram=<number> - return a list of projects with a specified ram quota
- ?storage=<number> - return a list of projects with a specified storage quota
- ?max_instances=<number> - return a list of projects with a specified max_instance quota

Sorting can be done by the following fields, specifying field name as a parameter to **?o=<field_name>**. To get a
descending sorting prefix field name with a **-**.

- ?o=name - sort by project name;
- ?o=project_group_name - sort by project's group names
- ?o=vcpu - sort by project's quota of vCPU number;
- ?o=ram - sort by project's quota of RAM;
- ?o=storage - sort by project's quota of storage;
- ?o=backup - sort by project's quota of backups;
- ?o=max_instances - sort by project's quota of instance number.
- ?o=project_groups__name - **deprecated**, use ?o=project_group instead.
- ?o=resource_quota__vcpu - **deprecated**, use ?=vcpu instead.
- ?o=resource_quota__ram - **deprecated**, use ?=ram instead.
- ?o=resource_quota__storage - **deprecated**, use ?=storage instead.
- ?o=resource_quota__max_instances - **deprecated**, use ?=max_instances instead.

Project permissions
-------------------

- Projects are connected to customers, whereas the project may belong to one customer only, and the customer may have multiple projects.
- Projects are connected to project groups, whereas the project may belong to multiple project groups, and the project group may contain multiple projects.
- Projects are connected to clouds, whereas the project may contain multiple clouds, and the cloud may belong to multiple projects.
- Staff members can list all available projects of any customer and create new projects.
- Customer owners can list all projects that belong to any of the customers they own. Customer owners can also create projects for the customers they own.
- Project administrators can list all the projects they are administrators in.
- Project managers can list all the projects they are managers in.

Optional filters are:

- ?username - matching of a related to the project user username
- ?full_name - matching of a related to the project user full name
- ?native_name - matching of a related to the project user native name
- ?project_group - matching of a project uuid
- ?role - matching of a user role type in a project:
    * 0 - admin
    * 1 - manager

Create a new project
--------------------

A new project can be created by users with staff privilege (is_staff=True) or customer owners.
Project resource quota is optional. Example of a valid request:

.. code-block:: http

    POST /api/projects/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "name": "Project A",
        "customer": "http://example.com/api/customers/6c9b01c251c24174a6691a1f894fae31/",
        "project_groups": [
            { "url": "http://localhost:8000/api/project-groups/b04f53e72e9b46949fa7c3a0ef52cd91/"}
        ]
    }


Deletion of a project
---------------------

Deletion of a project is done through sending a DELETE request to the project instance URI.
Valid request example (token is user specific):

.. code-block:: http

    DELETE /api/projects/6c9b01c251c24174a6691a1f894fae31/ HTTP/1.1
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com


Managing project roles
----------------------

Project permissions expresses connection of users to a project. Each project has two associated user groups that
represent project managers and administrators. The link is maintained
through **api/project-permissions/** endpoint.

Note that project group membership can be viewed and modified only by customer owners, corresponding project group
managers and staff users.

To list all visible links, run a GET query against a list.

.. code-block:: http

    GET /api/project-permissions/ HTTP/1.1
    Accept: application/json
    Authorization: Token 95a688962bf68678fd4c8cec4d138ddd9493c93b
    Host: example.com

Response will contain a list of project users and their brief data:

.. code-block:: http

    HTTP/1.0 200 OK
    Allow: GET, POST, HEAD, OPTIONS
    Content-Type: application/json
    X-Result-Count: 2

    [
        {
            "project": "http://example.com/api/projects/661ee58978d9487c8ac26c56836585e0/",
            "project_name": "bells.org",
            "role": "admin",
            "url": "http://example.com/api/project-permissions/4/",
            "user": "http://example.com/api/users/14471861a30d4293b7ef49340fc3080e/",
            "user_full_name": "",
            "user_native_name": ""
        },
        {
            "project": "http://example.com/api/projects/661ee58978d9487c8ac26c56836585e0/",
            "project_name": "bells.org",
            "role": "manager",
            "url": "http://example.com/api/project-permissions/5/",
            "user": "http://example.com/api/users/8f96d098e60642baa809707a8b118631/",
            "user_full_name": "",
            "user_native_name": ""
        }
    ]

To add a new user to the project, POST a new relationship to **api/project-permissions** endpoint specifying
project, user and the role of the user ('admin' or 'manager'):

.. code-block:: http

    POST /api/project-permissions/ HTTP/1.1
    Accept: application/json
    Authorization: Token 95a688962bf68678fd4c8cec4d138ddd9493c93b
    Host: example.com

    {
        "project": "http://example.com/api/projects/6c9b01c251c24174a6691a1f894fae31/",
        "role": "manager",
        "user": "http://example.com/api/users/82cec6c8e0484e0ab1429412fe4194b7/"
    }

To remove a user from a project group, delete corresponding connection (**url** field). Successful deletion
will return status code 204.

.. code-block:: http

    DELETE /api/project-permissions/42/ HTTP/1.1
    Authorization: Token 95a688962bf68678fd4c8cec4d138ddd9493c93b
    Host: example.com
