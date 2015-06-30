Customer list
-------------

To get a list of customers, run GET against **/api/customers/** as authenticated user. Note that a user can
only see connected customers:

- customers that the user owns
- customers that have a project where user has a role

Filtering of customer list is supported through HTTP query parameters, the following fields are supported:

- ?name=<customer name>
- ?native_name=<customer native name>
- ?abbreviation=<customer abbreviation>
- ?contact_details=<contact details>

Sorting is supported in ascending and descending order by specifying a field to an **?o=** parameter.

- ?o=name - sort by name
- ?o=native_name - sort by native name
- ?o=abbreviation - sort by abbreviation
- ?o=contact_details - sort by contact details

Customer permissions
--------------------

Customers are connected to users through roles, whereas user may have role "customer owner". Each customer may have multiple owners, and each user may own multiple customers.

Staff members can list all available customers and create new customers.

Customer owners can list all customers they own. Customer owners can also create new customers.

Project administrators can list all the customers that own any of the projects they are administrators in.

Project managers can list all the customers that own any of the projects they are managers in.


Create a new customer
---------------------

A new customer can only be created by users with staff privilege (is_staff=True). Example of a valid request:

.. code-block:: http

    POST /api/customers/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "name": "Customer A",
        "native_name": "Customer Ä",
        "abbreviation": "CA",
        "contact_details": "Luhamaa 29\r\n10128 Tallinn",
    }


Deletion of a customer
----------------------

Deletion of a customer is done through sending a DELETE request to the customer instance URI. Please note,
that if a customer has connected projects or project groups, deletion request will fail with 409 response code.

Valid request example (token is user specific):

.. code-block:: http

    DELETE /api/customers/6c9b01c251c24174a6691a1f894fae31/ HTTP/1.1
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

Managing customer owners
------------------------

Each customer is associated with a group of users that represent customer owners. The link is maintained
through **api/customer-permissions/** endpoint.

To list all visible links, run a GET query against a list.

.. code-block:: http

    GET /api/customer-permissions/ HTTP/1.1
    Accept: application/json
    Authorization: Token 95a688962bf68678fd4c8cec4d138ddd9493c93b
    Host: example.com

Response will contain a list of customer owners and their brief data:

.. code-block:: http

    HTTP/1.0 200 OK
    Allow: GET, POST, HEAD, OPTIONS
    Content-Type: application/json
    X-Result-Count: 2

    [
        {
            "customer": "http://example.com/api/customers/6c9b01c251c24174a6691a1f894fae31/",
            "customer_name": "Ministry of Bells",
            "customer_native_name": "Ministry of Bälls",
            "role": "owner",
            "url": "http://example.com/api/customer-permissions/1/",
            "user": "http://example.com/api/users/5b1e44cea92b41778a5300968278b2cd/",
            "user_full_name": "",
            "user_native_name": ""
        },
        {
            "customer": "http://example.com/api/customers/6c9b01c251c24174a6691a1f894fae31/",
            "customer_name": "Ministry of Bells",
            "customer_native_name": "Ministry of Bälls",
            "role": "owner",
            "url": "http://example.com/api/customer-permissions/2/",
            "user": "http://example.com/api/users/7dfffaa90e154271bd021ec03d7ee924/",
            "user_full_name": "",
            "user_native_name": ""
        }
    ]

Supported filters are:

- ?username - matching of a related to the customer user username
- ?full_name - matching of a related to the customer user full name
- ?native_name - matching of a related to the customer user native name
- ?customer - matching of a customer uuid
- ?role - matching of a user role type in a customer:
    * supported choices:
        * 0 **deprecated**, use *owner* instead

To add a new user to the customer, POST a new relationship to **customer-permissions** endpoint:

.. code-block:: http

    POST /api/customer-permissions/ HTTP/1.1
    Accept: application/json
    Authorization: Token 95a688962bf68678fd4c8cec4d138ddd9493c93b
    Host: example.com

    {
        "customer": "http://example.com/api/customers/6c9b01c251c24174a6691a1f894fae31/",
        "role": "owner",
        "user": "http://example.com/api/users/82cec6c8e0484e0ab1429412fe4194b7/"
    }

To remove a user from a customer owner group, delete corresponding connection (**url** field). Successful deletion
will return status code 204.

.. code-block:: http

    DELETE /api/customer-permissions/71/ HTTP/1.1
    Authorization: Token 95a688962bf68678fd4c8cec4d138ddd9493c93b
    Host: example.com


Customer estimated price
------------------------

To get customer estimated price - issue GET request against **/api/customers/<customer_uuid>/estimated_price/**
 endpoint.
