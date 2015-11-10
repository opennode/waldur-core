Security group list
-------------------

To get a list of Security Groups and security group rules, run GET against *api/security-groups/* as authenticated user.

Supported filters:

- ?name=<group_name> - only groups with defined name
- ?description=<description> - only groups where description starts with defined one
- ?project=<project_uuid> - only groups connected to a defined cloud
- ?cloud=<cloud_uuid> - only groups connected to a defined project
- ?state=<state> - choices: New, Creation Scheduled, Creating, Sync Scheduled, Syncing, In Sync, Erred

When instantiating a new instance, setting both **project** and **cloud** filters will result in a proper set of
security groups for selection.

Example of valid request (token is user specific):

.. code-block:: http

    GET /api/security-groups/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com


Valid response example:

.. code-block:: http

    HTTP/1.0 200 OK
    Content-Type: application/json
    Vary: Accept
    Allow: GET, HEAD, OPTIONS
    X-Result-Count: 1

    [
        {
            "url": "http://example.com/api/security-groups/1b07456342b44dc49b80e7a63aed8572/",
            "uuid": "1b07456342b44dc49b80e7a63aed8572",
            "name": "http",
            "state": "Syncing",
            "description": "Security group for web servers",
            "rules": [
                {
                    "id": 13,
                    "protocol": "tcp",
                    "from_port": 80,
                    "to_port": 80,
                    "cidr": "0.0.0.0/0",
                }
            ],
            "cloud_project_membership": {
                "url": "http://example.com/api/project-cloud-memberships/4/",
                "project": "http://example.com/api/projects/46915c169bd34ea19fbe20ccfbbff721/",
                "project_name": "Project uKnz",
                "cloud": "http://example.com/api/clouds/194157833b3b4ad2b18d71cf9678431f/",
                "cloud_name": "CloudAccount of Customer wJsCGu (rUzCLtuvdYHb)"
            }
        }
    ]


Create a security group
-----------------------

To create a new security group, issue a POST with security group details to **/api/security-groups/**. This will
create new security group and start its synchronization with OpenStack.

Example of a request:

.. code-block:: http

    POST /api/users/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "name": "Security group name",
        "description": "description",
        "rules": [
            {
                "protocol": "tcp",
                "from_port": 1,
                "to_port": 10,
                "cidr": "10.1.1.0/24"
            },
            {
                "protocol": "udp",
                "from_port": 10,
                "to_port": 8000,
                "cidr": "10.1.1.0/24"
            }
        ],
        "cloud_project_membership": {
            "url": "http://127.0.0.1:8000/api/project-cloud-memberships/229/"
        }
    }


Update a security group
-----------------------

Security group name, description and rules can be updated. To execute update request make PATCH request with details
to **/api/security-groups/<security-group-uuid>/**. This will update security group in database and start its
synchronization with OpenStack. To leave old security groups add old rule id to list of new rules (note that exist rule
cannot be updated, if endpoint receives id and some other attributes, it uses only id for rule identification).

.. code-block:: http

    POST /api/users/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "name": "Security group new name",
        "rules": [
            {
                "id": 13,
            },
            {
                "protocol": "udp",
                "from_port": 10,
                "to_port": 8000,
                "cidr": "10.1.1.0/24"
            }
        ],
    }


Delete a security group
-----------------------

To schedule security group deletion - issue DELETE request against */api/security-groups/<security-group-uuid>/*.
Endpoint will return 202 if deletion was scheduled successfully.