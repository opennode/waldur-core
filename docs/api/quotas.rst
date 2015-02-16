Getting quota limit and usage
-----------------------------

To get an actual value for object quotas limit and usage (in MiB) issue a GET request against **/api/<objects>/** or **/api/<objects>/<object_uuid>/**

Currently you can get project quotas at **/api/projects/** or **/api/projects/<uuid>/** and cloud project membership quotas at **/api/project-cloud-memberships/** or **/api/project-cloud-memberships/<id>/**

Example:

.. code-block:: http

    GET /api/projects/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com
    {
        ...
        "name": "ProjectA"
        "quotas": [
            {
                "url": "http://example.com/api/quotas/0f973ff855e74161979885e751473036/",
                "uuid": "0f973ff855e74161979885e751473036",
                "name": "vcpu",
                "limit": 20.0,
                "usage": 0.0,
                "owner": "http://example.com/api/projects/ddff7ad4c37c4ced8fa727ad9472409a/"
            },
            {
                "url": "http://example.com/api/quotas/afb6284c13bf4a99a05e2f18f9a5896c/",
                "uuid": "afb6284c13bf4a99a05e2f18f9a5896c",
                "name": "ram",
                "limit": 1024.0,
                "usage": 0.0,
                "owner": "http://example.com/api/projects/ddff7ad4c37c4ced8fa727ad9472409a/"
            },
            {
                "url": "http://example.com/api/quotas/85742e63c27e4bf7abf1d6dbf56492ab/",
                "uuid": "85742e63c27e4bf7abf1d6dbf56492ab",
                "name": "storage",
                "limit": 2048.0,
                "usage": 0.0,
                "owner": "http://example.com/api/projects/ddff7ad4c37c4ced8fa727ad9472409a/"
            },
            {
                "url": "http://example.com/api/quotas/40cc868934e04833b39e3578ab796217/",
                "uuid": "40cc868934e04833b39e3578ab796217",
                "name": "max_instances",
                "limit": 10.0,
                "usage": 0.0,
                "owner": "http://example.com/api/projects/ddff7ad4c37c4ced8fa727ad9472409a/"
            }
        ],
        ...
    }


To get all quotas for user issue a GET request against **/api/quotas/**

Example:

.. code-block:: http

    GET /api/projects/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com
    [
        ...
        {
            "url": "http://example.com/api/quotas/6ad5f49d6d6c49648573b2b71f44a42b/",
            "uuid": "6ad5f49d6d6c49648573b2b71f44a42b",
            "name": "vcpu",
            "limit": -1.0,
            "usage": 0.0,
            "owner": "http://example.com/api/projects/5f7ec56c529c4745842020e8e93597a8/"
        },
        {
            "url": "http://example.com/api/quotas/0725aa77f33b46a2b966669c626248f4/",
            "uuid": "0725aa77f33b46a2b966669c626248f4",
            "name": "ram",
            "limit": -1.0,
            "usage": 0.0,
            "owner": "http://example.com/api/projects/5f7ec56c529c4745842020e8e93597a8/"
        },
        {
            "url": "http://example.com/api/quotas/39ab2acd59924ee6beb461f4a265c110/",
            "uuid": "39ab2acd59924ee6beb461f4a265c110",
            "name": "storage",
            "limit": -1.0,
            "usage": 0.0,
            "owner": "http://example.com/api/projects/5f7ec56c529c4745842020e8e93597a8/"
        },
        {
            "url": "http://example.com/api/quotas/b4601b3490914b82aa2afd023a54a2ec/",
            "uuid": "b4601b3490914b82aa2afd023a54a2ec",
            "name": "max_instances",
            "limit": -1.0,
            "usage": 0.0,
            "owner": "http://example.com/api/projects/5f7ec56c529c4745842020e8e93597a8/"
        },
        {
            "url": "http://example.com/api/quotas/ef8ffb2f25ed472aa2debca7229a409d/",
            "uuid": "ef8ffb2f25ed472aa2debca7229a409d",
            "name": "vcpu",
            "limit": -1.0,
            "usage": 10.0,
            "owner": "http://example.com/api/projects/5eede44757a14986ab6f326a2ed0893d/"
        },
        ...
    ]


Setting quota limit and usage
-----------------------------

To set quota limit or usage issue PUT request at **/api/quotas/<quota uuid>** with new usage and/or limit values

.. code-block:: http

    POST /api/qutoas/6ad5f49d6d6c49648573b2b71f44a42b/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "limit": 2000.0,
        "usage": 0.0
    }
