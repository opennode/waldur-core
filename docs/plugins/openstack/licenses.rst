Listing licenses
----------------

Licenses can be listed by sending GET to **/api/openstack-licenses/**.
Filtering by customers is supported through **?customer=CUSTOMER_UUID** filter.

Example response:

.. code-block:: http

    HTTP/1.0 200 OK
    Allow: GET, POST, HEAD, OPTIONS
    Content-Type: application/json
    X-Result-Count: 2

    [
        {
            "instance": "http://example.com/api/openstack-instances/7a823b0074d34873a754cea9190e046e/",
            "group": "license-application",
            "type": "postgresql",
            "name": "9.4"
        },
        {
            "instance": "http://example.com/api/openstack-instances/7a823b0074d34873a754cea9190e046e/",
            "group": "license-os",
            "type": "centos7",
            "name": "CentOS Linux x86_64"
        }
    ]


Licenses statistics
-------------------

It is possible to issue queries to NodeConductor to get aggregate statistics about instance licenses.
Query is done against **/api/openstack-licenses/stats/** endpoint. Queries can be run by all users with
answers scoped by their visibility permissions of instances. By default queries are aggregated by license name.

Supported aggregate queries are:

- ?aggregate=name - by license name
- ?aggregate=type - by license type
- ?aggregate=project_group - by project groups
- ?aggregate=project - by projects
- ?aggregate=customer - by customer

Note: aggregate parameters can be combined to aggregate by several fields. For example,
*?aggregate=name&aggregate=type&aggregate=project* will aggregate result by license name,
license_type and project group.

Supported filters:

- ?customer=customer_uuid
- ?name=license_name
- ?type=license_type
