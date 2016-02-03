Service types
-------------

To get a list of supported service types, run GET against **/api/service-metadata/** as an authenticated user.
Example of a request:

.. code-block:: http

    GET /api/services/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "Oracle": {
            "url": "http://example.com/api/oracle/",
            "service_project_link_url": "http://example.com/api/oracle-service-project-link/",
            "resources": {
                "Database": "http://example.com/api/oracle-databases/"
            }
        },
        "OpenStack": {
            "url": "http://example.com/api/openstack/",
            "service_project_link_url": "http://example.com/api/openstack-service-project-link/",
            "properties": {
                "Flavor": "http://example.com/api/openstack-flavors/",
                "Image": "http://example.com/api/openstack-images/",
                "SecurityGroup": "http://example.com/api/openstack-security-groups/"
            },
            "resources": {
                "Instance": "http://example.com/api/openstack-instances/"
            }
        },
        "DigitalOcean": {
            "url": "http://example.com/api/digitalocean/",
            "service_project_link_url": "http://example.com/api/digitalocean-service-project-link/",
            "properties": {
                "Image": "http://example.com/api/digitalocean-images/",
                "Region": "http://example.com/api/digitalocean-regions/",
                "Size": "http://example.com/api/digitalocean-sizes/"
            },
            "resources": {
                "Droplet": "http://example.com/api/digitalocean-droplets/"
            }
        }
    }

Use an endpoint from the returned list in order to create new service.

List services
-------------

To list all services without regard to its type, run GET against **/api/services/** as an authenticated user.

Filtering of services list is supported through HTTP query parameters, the following fields are supported:

- ?name - case insensitive matching of a service name
- ?customer=<customer uuid>
- ?project_uuid=<project uuid>
- ?shared=<True|False>

Sorting can be done by specifying field name as a parameter to **?o=<field_name>**

To list services of specific type issue GET to specific endpoint from a list above as a customer owner.
Individual endpoint used for every service type.
Example:

.. code-block:: http

    GET /api/openstack/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    [
        {
            "uuid": "a66f449fab9f4b999c6be0e32d643059",
            "url": "http://www.example.com/api/openstack/a66f449fab9f4b999c6be0e32d643059/",
            "name": "Stratus",
            "projects": [],
            "customer": "http://www.example.com/api/customers/b3b0d890cab244b88429db838ead737a/",
            "customer_uuid": "b3b0d890cab244b88429db838ead737a",
            "customer_name": "Ministry of Bells",
            "customer_native_name": "",
            "settings": "http://www.example.com/api/service-settings/beed810ccec24dd786ed9c79d7fb72fe/",
            "state": "Erred",
            "error_message": "Unable to authenticate you.",
            "resources_count": 0
        },
        {
            "uuid": "cc83b515a4364a4699a6b36f99b39381",
            "url": "http://www.example.com/api/openstack/cc83b515a4364a4699a6b36f99b39381/",
            "name": "Cumulus",
            "projects": [],
            "customer": "http://www.example.com/api/customers/5bf7c7f1c67842849cbfc0b544d67056/",
            "customer_uuid": "5bf7c7f1c67842849cbfc0b544d67056",
            "customer_name": "Ministry of Whistles",
            "customer_native_name": "",
            "settings": "http://www.example.com/api/service-settings/2b688349377c4a28bf929ba0f60d6f46/",
            "state": "In Sync",
            "error_message": "",
            "resources_count": 10
        }
    ]

Create new service
------------------

To create a service, issue a POST to specific endpoint from a list above as a customer owner.
Individual endpoint used for every service type.

You can create service based on shared service settings. Example:

.. code-block:: http

    POST /api/digitalocean/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "name": "Common DigitalOcean",
        "customer": "http://example.com/api/customers/1040561ca9e046d2b74268600c7e1105/",
        "settings": "http://example.com/api/service-settings/93ba615d6111466ebe3f792669059cb4/"
    }

Or provide your own credentials. Example:

.. code-block:: http

    POST /api/oracle/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "name": "My Oracle",
        "customer": "http://example.com/api/customers/1040561ca9e046d2b74268600c7e1105/",
        "backend_url": "https://oracle.example.com:7802/em",
        "username": "admin",
        "password": "secret"
    }


Project-service connection list
-------------------------------

In order to be able to provision resources, service must first be linked to a project. To do that,
POST a connection between project and a service to service_project_link_url as stuff user or customer owner.

To remove a link, issue DELETE to URL of the corresponding connection as stuff user or customer owner.

To get a list of connections between a project and an service, run GET against service_project_link_url as authenticated user.
Note that a user can only see connections of a project where a user has a role.

Filtering of project-service connection list is supported through HTTP query parameters, the following fields are supported:

- ?service_uuid
- ?customer_uuid
- ?project_uuid

Example response:

.. code-block:: http

    GET /api/digitalocean-service-project-link/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    [
        {
            "url": "http://example.com/api/digitalocean-service-project-link/788/",
            "project": "http://example.com/api/projects/d35b89f61cb24e9ebb63255a4bef997c/",
            "project_name": "Web services",
            "project_uuid": "d35b89f61cb24e9ebb63255a4bef997c",
            "service": "http://example.com/api/digitalocean/f1cdaaf68d664a2a8e9aed09f6b80b40/",
            "service_name": "DigitalOceanTest",
            "service_uuid": "f1cdaaf68d664a2a8e9aed09f6b80b40",
            "state": "In Sync",
            "error_message": ""
        }
    ]


Import service resources
------------------------

To get a list of resources available for import, run GET against **/<service_endpoint>/link/** as an authenticated user.
Optionally project_uuid parameter can be supplied for services requiring it like OpenStack.

.. code-block:: http

    GET /api/openstack/08039f01c9794efc912f1689f4530cf0/link/?project_uuid=e5f973af2eb14d2d8c38d62bcbaccb33 HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    [
        {
            "id": "65207eb8-7fff-4ddc-9a70-9c6f280646c3",
            "name": "my-test"
            "status": "SHUTOFF",
            "created_at": "2015-06-11T10:30:43Z",
        },
        {
            "id": "bd5ec24d-9164-440b-a9f2-1b3c807c5df3",
            "name": "some-gbox"
            "status": "ACTIVE",
            "created_at": "2015-04-29T09:51:07Z",
        }
    ]

To import (link with NodeConductor) resource issue POST against the same endpoint with resource id.

.. code-block:: http

    POST /api/openstack/08039f01c9794efc912f1689f4530cf0/link/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "backend_id": "bd5ec24d-9164-440b-a9f2-1b3c807c5df3",
        "project": "http://example.com/api/projects/e5f973af2eb14d2d8c38d62bcbaccb33/"
    }
