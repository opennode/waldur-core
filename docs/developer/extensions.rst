NodeConductor Extensions
========================

NodeConductor extensions are developed as auto-configurable plugins. It's only
required to add desired application to INSTALLED_APPS. Extensions' URL's will
be registered automatically if settings.NODECONDUCTOR['EXTENSIONS AUTOREGISTER']
is True, which is default.

The plugin is expected to expose of all the application to be included in the
``entry_points``, for example:

.. code-block:: python

    entry_points={
       'nodeconductor_extensions': (
           'nodeconductor_plugin_app = nodeconductor_plugin.app.urls',
           ),
    }


DigitalOcean Extension
======================

DigitalOcean service provides an interface to DigitalOcean and allows to provision and import Droplets.

DigitalOcean services list
--------------------------

To get a list of services, run GET against **/api/digitalocean/** as authenticated user.

Import Droplet
--------------

Get a list of droplet available for import in this service,
run GET against **/api/digitalocean/<service_uuid>/link/**

In order to link a Droplet with NodeConductor issue a POST to the same endpoint.
Example of a request:

.. code-block:: http

    POST /api/digitalocean/aadf9bf2370c406f9b1390f93928f9fa/link/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "backend_id": "4039243",
        "project": "http://example.com/api/projects/e5f973af2eb14d2d8c38d62bcbaccb33/"
    }
