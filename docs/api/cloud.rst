Cloud model
-----------

Cloud represents an instance of an account in a certain service accessible over APIs, for example OpenStack
IaaS instance.

The following relationships are true for cloud operations:

- Clouds belong to customers. A customer can have any number of clouds.
- Clouds are connected with projects, whereas the cloud may be linked to multiple projects, and the project may
  be linked multiple clouds.
- Staff members can list all available clouds for any project and/or customer and create new clouds.
- Customer owners can list all clouds that belong to any of the customers they own. Customer owners can also create
  clouds for the customers they own.
- Project administrators can list all the clouds that are connected to any of the projects they are administrators in.
- Project managers can list all the clouds that are connected to any of the projects they are managers in.

Cloud list
----------

To get a list of cloud, run GET against **/api/clouds/** as authenticated user.

Filtering cloud list is supported through HTTP query parameters, the following fields are supported:

- ?name=<cloud name>
- ?customer=<customer uuid>
- ?customer_name=<customer native name>
- ?customer_native_name=<customer native name>
- ?project=<uuid of a connected project>
- ?project_name=<name of a connected project>

Note that all *_name* fields are using partial matching for searching.

Create a cloud
--------------

To create a new cloud (account in IaaS), issue a POST with cloud details to **/api/clouds/** as a customer owner.
Example of a request:

.. code-block:: http

    POST /api/users/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "customer": "http://example.com/api/customers/2aadad6a4b764661add14dfdda26b373/",
        "name": "new cloud"
    }

Link cloud to a project
-----------------------
In order to be able to provision instance using a cloud account, it must first be linked to a project. To do that,
POST a connection between project and a cloud to **/api/project-cloud-memberships/** as stuff user or customer owner.
For example,

.. code-block:: http

    POST /api/project-cloud-memberships/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "project": "http://example.com/api/projects/661ee58978d9487c8ac26c56836585e0/",
        "cloud": "http://example.com/api/clouds/736038dc5cac47309111916eb6fe802d/",
    }

To remove a link, issue DELETE to URL of the corresponding connection as stuff user or customer owner.

Any modification of a cloud in unstable state is prohibited and will fail with 409 response code.

Project-cloud connection list
-----------------------------
To get a list of connections between project and a cloud, run GET against **/api/project-cloud-memberships/**
as authenticated user. Note that a user can only see connections of a project where a user has a role.

Supported filters:

- ?cloud=<cloud_UUID>
- ?project=<project_UUID>
