Manage key in instance
----------------------

Authenticated user with project administrator role or with staff privilege (is_staff=True) during instance creation
should link instance to user's SSH public key. Example of valid request:

.. code-block:: http

    POST /api/instances/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "name": "test VM",
        "template": "http://example.com/api/iaas-templates/1ee385bc043249498cfeb8c7e3e079f0/",
        "flavor": "http://example.com/api/flavors/c3c546b92845431188636d8f97df223c/",
        "project": "http://example.com/api/projects/661ee58978d9487c8ac26c56836585e0/",
        "ssh_public_key": "http://example.com/api/keys/6fbd6b24246f4fb38715c29bafa2e5e7/",
    }

Authenticated user can see public key in instance that belong to a project where a user has a role.

Example of a valid request:

.. code-block:: http

    GET /api/instances/cc37a3de4b85450cab3b2190d965c82f/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

Example of a valid response:

.. code-block:: http

    HTTP/1.0 200 OK
    Allow: GET, POST, HEAD, OPTIONS
    Content-Type: application/json
    X-Result-Count: 2

    {
        "url": "http://example.com/api/instances/2751a59a41834b079936bc2142ddb22f/",
        "uuid": "2751a59a41834b079936bc2142ddb22f",
        "name": "test VM",
        "description": "description1",
        "start_time": "2014-10-22T08:12:55.028Z",
        "template": "http://example.com/api/iaas-templates/7826f6ab0e32490b9f408de41bab2458/",
        "template_name": "template11",
        "cloud": "http://example.com/api/clouds/861d830b42fa412f93e7c3f94a29ed6b/",
        "cloud_name": "cloud1",
        "flavor": "http://example.com/api/flavors/c7d3f71b3b6241c7a115b0c44c1defcb/",
        "flavor_name": "flavor1",
        "project": "http://example.com/api/projects/5571948e218949bb9474fb868c366e8c/",
        "project_name": "Project1",
        "customer": "http://example.com/api/customers/4648d37d23ca434bb8cb88b6defc3d20/",
        "customer_name": "Customer1",
        "ssh_public_key": "http://example.com/api/keys/e49f536565e646f9a4a6b2dbd57fad37/",
        "ssh_public_key_name": "ssh_public_key1",
        "project_groups": [],
        "security_groups": [],
        "ips": [
        "211.30.138.236",
        "29.174.45.57",
        "20.121.203.247"
        ],
        "state": "Provisioning Scheduled",
        "backups": [],
        "backup_schedules": []
    }
