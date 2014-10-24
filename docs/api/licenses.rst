Template licenses
-----------------

Template license is defined as an abstract consumable.
Every template is potentially connected to zero or more template licenses.

Templates Instances is available only for administrators.

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
        "service_type": models.TemplateLicense.Services.IAAS,
        "setup_fee": 10,
        "monthly_fee": 10
    }


Partial update existing template license
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Example of a valid request:

.. code-block:: http

    PATCH /api/template-licenses/6c9b01c251c24174a6691a1f894fae31/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {"name": "new_name"}


Delete template license
^^^^^^^^^^^^^^^^^^^^^^^

Example of a valid request:

.. code-block:: http

    DELETE /api/template-licenses/6c9b01c251c24174a6691a1f894fae31/ HTTP/1.1
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com


Template licenses list
^^^^^^^^^^^^^^^^^^^^^^

Template licenses can be filtered by customers, customer uuid have to be sent as GET parameter



Instance licenses
-----------------

Instance licenses automatically appears on new instance creation.
All licenses from new instance template are copied and attached to instance as Instance licenses.
Instance licenses are returned as instance field "instance_licenses".

Instance licenses statistics
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

It is possible to issue queries to NC to get aggregate statistics about instance licenses.
Query is done against /api/template-licenses/stats/ endpoint. Queries can be run by all users with a answers scoped by their visibility permissions for instances. By default queries is aggregated by license name.

Supported aggregate queries are:

    - ?aggregate=project_name  -  by project names, result example: [{'project_name': 'project_1', 'count': 3}, ..];
    - ?aggregate=project_group  -  by project groups, result example: [{'project_group': 'proejct_group1', 'count': 2}, ..];
    - ?aggregate=license_type  - by license type, result example: [{'license_type': 'license_type1', 'count': 2}, ..];
    - no parameter  - by license name, result example: [{'name': 'license_name1', 'count': 4}, ..];
