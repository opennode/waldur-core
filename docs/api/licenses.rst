Template licenses
-----------------

Template license is defined as an abstract consumable.
Every template is potentially connected to zero or more template licenses.

Management of the templates license instances is available only for staff users.

Create new template license
^^^^^^^^^^^^^^^^^^^^^^^^^^^

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
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Example of a valid request:

.. code-block:: http

    PUT /api/template-licenses/6c9b01c251c24174a6691a1f894fae31/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "name": "new license",
        "license_type": "new license type",
        "service_type": "IaaS",
        "setup_fee": 10,
        "monthly_fee": 15
    }


Partial update of an existing template license
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Example of a valid request:

.. code-block:: http

    PATCH /api/template-licenses/6c9b01c251c24174a6691a1f894fae31/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {"name": "new_name"}


Deleting a template license
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Example of a valid request:

.. code-block:: http

    DELETE /api/template-licenses/6c9b01c251c24174a6691a1f894fae31/ HTTP/1.1
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com


Listing template licenses
^^^^^^^^^^^^^^^^^^^^^^^^^

Template licenses can be listed by sending GET to **/api/template-licenses/**.
Filtering by customers is supported through **?customer=CUSTOMER_UUID** filter.

Instance licenses
-----------------

Instance licenses are automatically cloned from the Template licenses when a new instance is created.
Instance licenses are listed in Instance rendering as a field "instance_licenses".

Instance licenses statistics
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

It is possible to issue queries to NodeConductor to get aggregate statistics about instance licenses.
Query is done against **/api/template-licenses/stats/** endpoint. Queries can be run by all users with
answers scoped by their visibility permissions of instances. By default queries are aggregated by license name.

Supported aggregate queries are:

- ?aggregate=project_name  -  by project names, result example: [{'project_name': 'project_1', 'count': 3}, ..];
- ?aggregate=project_group  -  by project groups, result example: [{'project_group': 'proejct_group1', 'count': 2}, ..];
- ?aggregate=license_type  - by license type, result example: [{'license_type': 'license_type1', 'count': 2}, ..];
- no parameter  - by license name, result example: [{'name': 'license_name1', 'count': 4}, ..];