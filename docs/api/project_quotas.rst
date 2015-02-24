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