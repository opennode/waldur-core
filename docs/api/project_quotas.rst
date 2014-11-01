Create a new project quota
--------------------------

A new project quota can be created within project by users with staff privilege (is_staff=True) or customer owners.

Example of a valid request (token is user specific):

.. code-block:: http

    POST /api/projects/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "name": "Project A",
        "customer": "http://example.com/api/customers/6c9b01c251c24174a6691a1f894fae31/",
        "resource_quota": {
                "vcpu": 2,
                "ram": 2.0,
                "storage": 36.15540199549969,
                "backup": 113.5527366632655
            },
    }

Managing project quota
----------------------

Quota of the existing project can be changed by users with staff privilege (is_staff=True) or customer owners.

Example of a valid request (token is user specific):

.. code-block:: http

    PATCH /api/projects/6c9b01c251c24174a6691a1f894fae31/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "resource_quota": {
                "vcpu": 2,
                "ram": 2.0,
                "storage": 36.15540199549969,
                "backup": 113.5527366632655
            },
    }

To fully update quota of the existing project, PUT a new quota to the project's url
specifying name, customer and quota:

.. code-block:: http

    PUT /api/projects/6c9b01c251c24174a6691a1f894fae31/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "name": "Project A",
        "customer": "http://example.com/api/customers/6c9b01c251c24174a6691a1f894fae31/",
        "resource_quota": {
                "vcpu": 2,
                "ram": 2.0,
                "storage": 36.15540199549969,
                "backup": 113.5527366632655
            },
    }
