Service
=======

List OpenStack services
-----------------------

To list OpenStack services, issue GET against **/api/openstack/** as a customer owner.

Example of a request:

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

- ?name=<service name>
- ?customer=<customer uuid>
- ?project_uuid=<project uuid>


Create OpenStack service
------------------------

To create a service, issue a POST to **/api/openstack/** as a customer owner.

You can create service based on shared service settings. Example:

.. code-block:: http

    POST /api/openstack/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "name": "Common OpenStack",
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
        "name": "My OpenStack",
        "customer": "http://example.com/api/customers/1040561ca9e046d2b74268600c7e1105/",
        "backend_url": "http://keystone.example.com:5000/v2.0",
        "username": "admin",
        "password": "secret"
    }

To remove OpenStack service, issue DELETE against **/api/openstack/<service_uuid>/** as staff user or customer owner.


Update OpenStack service
------------------------

To update OpenStack service issue PUT or PATCH against **/api/openstack/<service_uuid>/** as a customer owner.
You can only update service's name.

Example of a request:

.. code-block:: http

    PUT /api/openstack/c6526bac12b343a9a65c4cd6710666ee/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "name": "My cloud"
    }


Link OpenStack service to a project
-----------------------------------

In order to be able to provision OpenStack resources, it must first be linked to a project. To do that,
POST a connection between project and a service to **/api/openstack-service-project-link/**
as stuff user or customer owner.

Example of a request:

.. code-block:: http

    POST /api/openstack-service-project-link/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "project": "http://example.com/api/projects/e5f973af2eb14d2d8c38d62bcbaccb33/",
        "service": "http://example.com/api/openstack/b0e8a4cbd47c4f9ca01642b7ec033db4/"
    }

To remove a link, issue DELETE to url of the corresponding connection as stuff user or customer owner.

