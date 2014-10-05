Version
-------

In order to retrieve current version of the NodeConductor authenticated user
should send a GET request to /api/version/.

Valid response example:

.. code-block:: http

    GET /api/version/
    HTTP 200 OK
    Content-Type: application/json
    Vary: Accept
    Allow: OPTIONS, GET

    {
    "version": "0.1.0-dev"
    }

