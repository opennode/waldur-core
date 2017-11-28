Version
-------

In order to retrieve current version of the Waldur authenticated user
should send a GET request to **/api/version/**.

Valid request example (token is user specific):

.. code-block:: http

    GET /api/version/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com


Valid response example:

.. code-block:: http

    HTTP/1.0 200 OK
    Content-Type: application/json
    Vary: Accept
    Allow: OPTIONS, GET

    {
        "version": "0.3.0"
    }
