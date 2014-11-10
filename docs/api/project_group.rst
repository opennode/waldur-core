Project group list
------------------

To get a list of projects groups, run GET against */api/project-groupss/* as authenticated user. Note that a user can
only see connected project groups:

- project groups that the user owns as a customer;
- project groups with projects where user has a role.

Optional filters are:

- ?name= - partial match filtering by project group name
- ?customer= - partial match filtering by customer name

Ordering can be done by setting an ordering field with **?o=<field_name>**. Supported field names are:

- ?o=name - sort by project group name in ascending order;
- ?o=-name - sort by project group name in descending order;

- ?o=customer__name - sort by customer name in ascending order;
- ?o=-customer__name - sort by customer name in descending order.


Create a new project group
--------------------------

A new project can be created by users with staff privilege (is_staff=True) or customer owners.
Project resource quota is optional. Example of a valid request:

.. code-block:: http

    POST /api/project-groups/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "name": "Project A",
        "customer": "http://example.com/api/customers/6c9b01c251c24174a6691a1f894fae31/",
    }


Deletion of a project group
---------------------------

Deletion of a project is done through sending a DELETE request to the project group instance URI.
Valid request example (token is user specific):

.. code-block:: http

    DELETE /api/project-groups/6c9b01c251c24174a6691a1f894fae31/ HTTP/1.1
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com


Managing project group roles
----------------------------

Project group permissions expresses connection of users to project groups. A single role is supported - Project Group
manager.

Management is done through **api/project-group-permissions/** endpoint.

To list all visible links, run a GET query against a list.

.. code-block:: http

    GET /api/project-group-permissions/ HTTP/1.1
    Accept: application/json
    Authorization: Token 95a688962bf68678fd4c8cec4d138ddd9493c93b
    Host: example.com

Response will contain a list of project groups' users and their brief data:

.. code-block:: http

    HTTP/1.0 200 OK
    Allow: GET, POST, HEAD, OPTIONS
    Content-Type: application/json
    X-Result-Count: 2

    [
        {
            "url": "http://example.com/api/project-group-permissions/4/",
            "project_group": "http://example.com/api/projects/661ee58978d9487c8ac26c56836585e0/",
            "project_group_name": "whistles.org",
            "role": "manager",
            "user": "http://example.com/api/users/14471861a30d4293b7ef49340fc3080e/",
            "user_full_name": "",
            "user_native_name": ""
        },
        {
            "url": "http://example.com/api/project-group-permissions/5/",
            "project_group": "http://example.com/api/project_group/661ee58978d9487c8ac26c56836585e0/",
            "project_group_name": "bells.org",
            "role": "manager",
            "user": "http://example.com/api/users/8f96d098e60642baa809707a8b118631/",
            "user_full_name": "",
            "user_native_name": ""
        }
    ]

To add a new user to the project group, POST a new relationship to **api/project-permissions** endpoint specifying
project, user and the role of the user (currently the only role is '1' - project group manager):

.. code-block:: http

    POST /api/project-permissions/ HTTP/1.1
    Accept: application/json
    Authorization: Token 95a688962bf68678fd4c8cec4d138ddd9493c93b
    Host: example.com

    {
        "project": "http://example.com/api/projects-groups/6c9b01c251c24174a6691a1f894fae31/",
        "role": "manager",
        "user": "http://example.com/api/users/82cec6c8e0484e0ab1429412fe4194b7/"
    }

To remove a user from a project group, delete corresponding connection (**url** field). Successful deletion
will return status code 204.

.. code-block:: http

    DELETE /api/project-group-permissions/42/ HTTP/1.1
    Authorization: Token 95a688962bf68678fd4c8cec4d138ddd9493c93b
    Host: example.com
