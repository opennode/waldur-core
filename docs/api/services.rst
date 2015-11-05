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
            "resources": {
                "Database": "http://example.com/api/oracle-databases/"
            }
        },
        "OpenStack": {
            "url": "http://example.com/api/clouds/",
            "resources": {
                "Instance": "http://example.com/api/iaas-resources/"
            }
        },
        "GitLab": {
            "url": "http://example.com/api/gitlab/",
            "resources": {
                "Project": "http://example.com/api/gitlab-projects/",
                "Group": "http://example.com/api/gitlab-groups/"
            }
        },
        "DigitalOcean": {
            "url": "http://example.com/api/digitalocean/",
            "resources": {
                "Droplet": "http://example.com/api/digitalocean-droplets/"
            }
        }
    }

Use an endpoint from the returned list in order to create new service.

List services
-------------

To list all services without regard to its type, run GET against **/api/services/** as an authenticated user.

Supported filters are:

- ?name - case insensitive matching of a resource name
- ?customer=<customer uuid>
- ?project_uuid=<project uuid>

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
            "customer_name": "Ministry of Bells",
            "customer_native_name": "",
            "settings": "http://www.example.com/api/service-settings/beed810ccec24dd786ed9c79d7fb72fe/"
        },
        {
            "uuid": "cc83b515a4364a4699a6b36f99b39381",
            "url": "http://www.example.com/api/openstack/cc83b515a4364a4699a6b36f99b39381/",
            "name": "Cumulus",
            "projects": [],
            "customer": "http://www.example.com/api/customers/5bf7c7f1c67842849cbfc0b544d67056/",
            "customer_name": "Ministry of Whistles",
            "customer_native_name": "",
            "settings": "http://www.example.com/api/service-settings/2b688349377c4a28bf929ba0f60d6f46/"
        }
    ]

Filtering of services list is supported through HTTP query parameters, the following fields are supported:

- ?customer=<customer uuid>

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
        "name": "My oracle",
        "customer": "http://example.com/api/customers/1040561ca9e046d2b74268600c7e1105/",
        "backend_url": "https://oracle.example.com:7802/em",
        "username": "admin",
        "password": "secret"
    }


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
