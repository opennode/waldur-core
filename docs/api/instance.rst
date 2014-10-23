Instance list
-------------

To get a list of instances, run GET against */api/instances/* as authenticated user. Note that a user can
only see connected instances:

- instances that belong to a project where a user has a role.
- instances that belong to a customer that a user owns.

Filtering of instance list is supported through HTTP query parameters, the following fields are supported:

- hostname
- customer_name
- state
- project
- project_group
- security_groups


Instance status
---------------

Each instance has a **status** field that defines its current state. Instance has a FSM that defines possible
state transitions. If a request is made to perform an operation on instance in incorrect state, a validation
error will be returned.

The UI can poll for status updates to provide feedback after submitting one of the longer running operations.

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
        "security_groups": [{"name": "security group name 1"}, {"name": security group name 2}]
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

Deletion of an instance
-----------------------

Deletion of an instance is done through sending a DELETE request to the instance URI.
Valid request example (token is user specific):

.. code-block:: http

    DELETE /api/instances/6c9b01c251c24174a6691a1f894fae31/ HTTP/1.1
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

NB! Only stopped instances can be deleted.

