IP mapping list
---------------

To get a list of IP mappings, run GET against */api/ip-mappings/* as authenticated user.

Supported filters are:

- ?project - matching of a project uuid
- ?private_ip - matching of a private IP address
- ?public_ip - matching of a public IP address

IP mapping permissions
----------------------

- Staff members can list all available IP mappings.
- Staff members can create, manage and delete IP mappings.
- Customer owners can list all IP mappings in all the projects that belong to any of the customers they own.
- Project administrators can list all IP mappings of the projects they are administrators in.
- Project managers can list all IP mappings of the projects they are managers in.

Create a new IP mapping
-----------------------

To create a new IP mapping, issue a POST to **/api/ip-mappings/** as a staff user.
Example of a request:

.. code-block:: http

    POST /api/ip-mappings/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "public_ip": "131.107.140.29",
        "private_ip": "10.242.22.8",
        "project": "http://example.com/api/projects/661ee58978d9487c8ac26c56836585e0/",
    }

Deletion of an IP mapping
-------------------------

Deletion of an IP mapping is done through sending a DELETE request to the IP mapping instance URI by staff user.
Valid request example (token is user specific):

.. code-block:: http

    DELETE /api/ip-mappings/5278e27237904f588be57e034be6d826/ HTTP/1.1
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

Updating a IP mapping
---------------------

Can be done by PUTing a new data to the IP mapping instance URI, i.e. **api/ip-mappings/<UUID>** by staff user.
Valid request example (token is user specific):

.. code-block:: http

    PUT /api/ip-mappings/5278e27237904f588be57e034be6d826/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "public_ip": "131.107.140.29",
        "private_ip": "10.242.22.8",
        "project": "http://example.com/api/projects/661ee58978d9487c8ac26c56836585e0/",
    }

To update a single field of the IP mapping instance, issue a PATCH to **/api/ip-mappings/<UUID>** as a staff user.
Valid request example (token is user specific):

.. code-block:: http

    PATCH /api/ip-mappings/5278e27237904f588be57e034be6d826/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "public_ip": "131.107.140.35",
    }
