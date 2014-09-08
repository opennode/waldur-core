========================
Authentication with REST
========================

NodeConductor uses token-based authentication.

In order to authenticate your requests first obtain from any of the supported token backends.
Then use the token in all the subsequent requests putting it into ``Authorization`` header:

.. code-block:: http

    GET /api/projects/ HTTP/1.1
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

Supported token backends
------------------------

Password based backend
^^^^^^^^^^^^^^^^^^^^^^

Endpoint url: ``/api-auth/password/``

Valid request example:

.. code-block:: http

    POST /api-auth/password/ HTTP/1.1
    Accept: application/json
    Content-Type: application/json
    Host: example.com

    {
        "username": "alice",
        "password": "$ecr3t"
    }

Success response example:

.. code-block:: http

    HTTP/1.0 200 OK
    Allow: POST, OPTIONS
    Content-Type: application/json
    Vary: Accept, Cookie

    {
        "token": "c84d653b9ec92c6cbac41c706593e66f567a7fa4"
    }

Field validation failure response example:

.. code-block:: http

    HTTP/1.0 401 UNAUTHORIZED
    Allow: POST, OPTIONS
    Content-Type: application/json

    {
        "password": ["This field is required."]
    }

Invalid credentials failure response example:

.. code-block:: http

    HTTP/1.0 401 UNAUTHORIZED
    Allow: POST, OPTIONS
    Content-Type: application/json

    {
        "detail": "Invalid username/password"
    }
