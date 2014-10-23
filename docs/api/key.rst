Key list
--------

To get a list of SSH keys, run GET against */api/keys/* as authenticated user.
Note that user can see only keys that he owns.

- Keys are injected to instances during creation. The owner of the key can log in to that instance.
- Project administrators can select what key will be injected to instance during instance provisioning.

Create a new key
----------------

A new SSH key can be created by any active users. Example of a valid request:

.. code-block:: http

    POST /api/keys/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "name": "ssh_public_key1",
        "public_key": "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDDURXDP5YhOQUYoDuTxJ84DuzqMJYJqJ8+SZT28
                       TtLm5yBDRLKAERqtlbH2gkrQ3US58gd2r8H9jAmQOydfvgwauxuJUE4eDpaMWupqquMYsYLB5f+vVGhdZbbzfc6DTQ2rY
                       dknWoMoArlG7MvRMA/xQ0ye1muTv+mYMipnd7Z+WH0uVArYI9QBpqC/gpZRRIouQ4VIQIVWGoT6M4Kat5ZBXEa9yP+9du
                       D2C05GX3gumoSAVyAcDHn/xgej9pYRXGha4l+LKkFdGwAoXdV1z79EG1+9ns7wXuqMJFHM2KDpxAizV0GkZcojISvDwuh
                       vEAFdOJcqjyyH4FOGYa8usP1 jhon@example.com",
    }

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
        "hostname": "test VM",
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
        "hostname": "test VM",
        "ssh_public_key": "http://example.com/api/keys/e49f536565e646f9a4a6b2dbd57fad37/",
        "ssh_public_key_name": "ssh_public_key1",
    }
