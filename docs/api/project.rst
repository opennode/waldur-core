Project list
-------------

To get a list of projects, run GET against */api/projects/* as authenticated user. Note that a user can
only see connected projects:

- projects that the user owns as a customer
- projects where user has a role

Create a new project
---------------------

A new project can be created by users with staff privilege (is_staff=True) or customer owners. Example of a valid request:

.. code-block:: http

    POST /api/projects/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "name": "Project A",
        "customer": "http://example.com/api/customers/6c9b01c251c24174a6691a1f894fae31/",
    }


Deletion of a project
----------------------

Deletion of a project is done through sending a DELETE request to the project instance URI.
Valid request example (token is user specific):

.. code-block:: http

    DELETE /api/projects/6c9b01c251c24174a6691a1f894fae31/ HTTP/1.1
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com


Managing project roles
----------------------

Each project has two associated user groups that represent project managers and administrators. The link is maintained
through **api/project-permissions/** endpoint.

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
