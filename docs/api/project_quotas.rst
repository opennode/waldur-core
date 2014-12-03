Create a new project quota
--------------------------

A new project quota can be created within project by users with staff privilege (is_staff=True) or customer owners.

The units of quotas relating to storage are defined in MiB_.

.. _MiB: http://en.wikipedia.org/wiki/Mebibyte

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
                "max_instances": 10
            },
    }

Getting project quota and usage
-------------------------------

To get an actual value for project quotas and project usage issue a GET request against **/api/projects/**.

Example of a valid response:

.. code-block:: http

    GET /api/projects/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com
    {
        ...
        "name": "Project A",
        "resource_quota": {
            "vcpu": 26,
            "ram": 229.0,
            "storage": 124.0,
            "max_instances": 199
        },
        "resource_quota_usage": {
            "vcpu": 22,
            "ram": 225.0,
            "storage": 113.0,
            "max_instances": 186
        },
        ...
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
                "max_instances": 11
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
                "max_instances": 11
            },
    }
