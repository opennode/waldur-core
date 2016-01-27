Oracle service provides an interface to Oracle Enterprise Manager.
Allows to provision a database resource.

Oracle services list
--------------------

To get a list of services, run GET against **/api/oracle/** as authenticated user.

Create an Oracle service
------------------------

To create a new Oracle service, issue a POST with service details to **/api/oracle/** as a customer owner.
Example of a request:

.. code-block:: http

    POST /api/oracle/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "name": "My Oracle"
        "customer": "http://example.com/api/customers/2aadad6a4b764661add14dfdda26b373/",
        "settings": "http://example.com/api/service-settings/668f3bb7a5994b69bdcb76c9df14ca60/"
    }

Settings must be of proper type and represent Oracle service.

Link service to a project
-------------------------
In order to be able to provision Oracle resources, it must first be linked to a project. To do that,
POST a connection between project and a service to **/api/oracle-service-project-link/** as stuff user or customer owner.
For example,

.. code-block:: http

    POST /api/oracle-service-project-link/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "project": "http://example.com/api/projects/e5f973af2eb14d2d8c38d62bcbaccb33/",
        "service": "http://example.com/api/oracle/b0e8a4cbd47c4f9ca01642b7ec033db4/"
    }

To remove a link, issue DELETE to URL of the corresponding connection as stuff user or customer owner.

Project-service connection list
-------------------------------
To get a list of connections between a project and an Oracle service, run GET against **/api/oracle-service-project-link/**
as authenticated user. Note that a user can only see connections of a project where a user has a role.

Oracle service properties
-------------------------

The following Oracle properties available and required to provision a database.
All properties are automatically pulled from service backend on service settings creation.

Zone
^^^^

To get a list of zones, run GET against **/api/oracle-zones/** as authenticated user.

Template
^^^^^^^^

To get a list of zones, run GET against **/api/oracle-templates/** as authenticated user.

Create an Oracle database
-------------------------

A new database can be created by users with project administrator role or with staff privilege (is_staff=True).
To create a database, client must define:

- name;
- description (optional);
- link to the project-service object;
- link to the template (it *must* be database platform template);
- link to the zone;
- link to user's public key (user owning this key will be able to log in to the instance);
- database sid;
- service name;
- username;
- password;

Example of a valid request:

.. code-block:: http

    POST /api/oracle-databases/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "name": "test DB",
        "description": "sample description",
        "template": "http://example.com/api/oracle-templates/cb0d820df3af45eba77e08b2f9b47809/",
        "zone": "http://example.com/api/oracle-zones/dc7e0485cab143d28fb3edbad2edaf6b/",
        "service_project_link": "http://example.com/api/oracle-service-project-link/1/",
        "ssh_public_key": "http://example.com/api/keys/6fbd6b24246f4fb38715c29bafa2e5e7/",
        "backend_database_sid": "demodb",
        "backend_service_name": "svc_demo",
        "username": "oracle",
        "password": "secret"
    }

Database display
----------------

Example rendering of the Database object:

.. code-block:: javascript

    [
        {
            "url": "http://example.com/api/oracle-databases/01387e7e8ebe4d57a5e8a5da6dd46a40/",
            "uuid": "01387e7e8ebe4d57a5e8a5da6dd46a40",
            "name": "test DB",
            "description": "sample description",
            "start_time": "2015-06-03T15:59:51.470Z",
            "service": "http://example.com/api/oracle/b0e8a4cbd47c4f9ca01642b7ec033db4/",
            "service_name": "My Oracle",
            "service_uuid": "b0e8a4cbd47c4f9ca01642b7ec033db4",
            "project": "http://example.com/api/projects/e5f973af2eb14d2d8c38d62bcbaccb33/",
            "project_name": "My Project",
            "project_uuid": "e5f973af2eb14d2d8c38d62bcbaccb33",
            "customer": "http://example.com/api/customers/1040561ca9e046d2b74268600c7e1105/",
            "customer_name": "Alice",
            "customer_native_name": "Alice D.",
            "customer_abbreviation": "AD",
            "project_groups": [
                {
                    "url": "http://example.com/api/project-groups/b04f53e72e9b46949fa7c3a0ef52cd91/",
                    "name": "Managers",
                    "uuid": "b04f53e72e9b46949fa7c3a0ef52cd91"
                }
            ],
            "state": "Online",
            "created": "2015-06-03T15:59:48.749Z",
            "backend_database_sid": "demodb",
            "backend_service_name": "svc_demo"
        }
    ]

Stopping/starting/restarting a database
-----------------------------------------

To stop/start/restart a database, run an authorized POST request against the database UUID,
appending the requested command.
Examples of URLs:

- POST /api/oracle-databases/01387e7e8ebe4d57a5e8a5da6dd46a40/start/
- POST /api/oracle-databases/01387e7e8ebe4d57a5e8a5da6dd46a40/stop/
- POST /api/oracle-databases/01387e7e8ebe4d57a5e8a5da6dd46a40/restart/

If database is in the state that does not allow this transition, error code will be returned.
