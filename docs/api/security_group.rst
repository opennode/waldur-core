Security group list
-------------------

To get a list of Security Groups and security group rules, run GET against *api/security-groups/* as authenticated user.

Supported filters:

- ?name=<group_name> - only groups with defined name
- ?description=<description> - only groups where description starts with defined one
- ?project=<project_uuid> - only groups connected to a defined cloud
- ?cloud=<cloud_uuid> - only groups connected to a defined project

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
            "description": "Security group for web servers",
            "rules": [
                {
                    "protocol": "tcp",
                    "from_port": 80,
                    "to_port": 80,
                    "ip_range": "0.0.0.0",
                    "netmask": 0
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