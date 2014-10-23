Template licenses
-----------------

Template license is defined as an abstract consumable.
Every template is potentially connected to zero or more template licenses.

Templates Instances is available only for administrators.

Create new template license
---------------------------

Example of a valid request:

.. code-block:: http

    POST /api/template-licenses/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "name": "license",
        "license_type": "license_type",
        "service_type": "IaaS",
        "setup_fee": 10,
        "monthly_fee": 10
    }


Update existing template license
--------------------------------

.. code-block:: http

    PATCH /api/template-licenses/6c9b01c251c24174a6691a1f894fae31/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {"name": "new_name"}


Delete template license
-----------------------

Example of a valid request:

.. code-block:: http

    DELETE /api/template-licenses/6c9b01c251c24174a6691a1f894fae31/ HTTP/1.1
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com


Template licenses list
----------------------

Template licenses can be filtered by customers, customer uuid have to be sent as GET parameter


