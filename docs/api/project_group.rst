Project group list
------------------

To get a list of projects groups, run GET against */api/project-groupss/* as authenticated user. Note that a user can
only see connected project groups:

- project groups that the user owns as a customer;
- project groups with projects where user has a role.

Optional filters are:

- ?name= - partial match filtering by project group name
- ?customer= - partial match filtering by customer name

Ordering can be done by setting an ordering field with **?o=<field_name>**. Supported field names are:

- ?o=name - sort by project group name in ascending order;
- ?o=-name - sort by project group name in descending order;

- ?o=customer__name - sort by customer name in ascending order;
- ?o=-customer__name - sort by customer name in descending order.


Create a new project group
--------------------------

A new project can be created by users with staff privilege (is_staff=True) or customer owners.
Project resource quota is optional. Example of a valid request:

.. code-block:: http

    POST /api/project-groups/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "name": "Project A",
        "customer": "http://example.com/api/customers/6c9b01c251c24174a6691a1f894fae31/",
    }


Deletion of a project group
---------------------------

Deletion of a project is done through sending a DELETE request to the project group instance URI.
Valid request example (token is user specific):

.. code-block:: http

    DELETE /api/project-groups/6c9b01c251c24174a6691a1f894fae31/ HTTP/1.1
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com
