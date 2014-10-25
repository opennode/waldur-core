Security group list
-------------------

To get a list of openstack security groups, run GET against *api/security-groups/* as authenticated user.

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
    X-Result-Count: 2

    [

        {
            "url": "http://example.com/api/security-groups/5b65998a80ba4af19b1b3a7d1b972fbf/",
            "uuid": "5b65998a80ba4af19b1b3a7d1b972fbf",
            "name": "default",
            "description": "Openstack security group",
            "protocol": 0,
            "from_port": 22,
            "to_port": 22,
            "ip_range": "10.2.6.30",
            "netmask": 24
        },
        {
            "url": "http://example.com/api/security-groups/16c55dad9b3048db8dd60e89bd4d85bc/",
            "uuid": "16c55dad9b3048db8dd60e89bd4d85bc",
            "name": "global_http",
            "description": "Allow web traffic from the Internet",
            "protocol": 1,
            "from_port": 80,
            "to_port": 80,
            "ip_range": "0.0.0.0",
            "netmask": 0
        },
    ]