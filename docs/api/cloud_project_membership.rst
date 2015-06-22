Project-cloud links
-------------------

A connection between a project and a cloud is represented through an object called membership (or link). A membership
can expose additional operations. Supported operations are listed below.


Links list
----------
List of memberships(links) is available at */api/project-cloud-memberships/* endpoint and support next filters:

- ?cloud=<cloud uuid>
- ?project=<project uuid>
- ?tenant_id=<id of tenant that is related to link>


Setting a project-cloud link quota
----------------------------------

A project quota can be set for a particular link between cloud and project. Only staff users can do that. In order
to set quota submit POST request to **/api/project-cloud-memberships/<pk>/set_quotas/**. The quota values are propagated
to the backend.

The following is a list of supported quotas. All values are expected to be integers:

- max_instance - maximal number of created instances.
- ram - maximal size of ram for allocation. In MiB_.
- storage - maximal size of storage for allocation. In MiB_.
- vcpu - maximal number of virtual cores for allocation.
- security_group_count - maximal number of created security groups.
- security_group_rule_count - maximal number of created security groups rules.

It is possible to update quotas by one or by submitting all the fields in one request. NodeConductor will attempt
to update the provided quotas. Please note, that if provided quotas are conflicting with the backend
(e.g. requested number of instances is below of the already existing ones), some quotas might not be applied.

.. _MiB: http://en.wikipedia.org/wiki/Mebibyte

Example of a valid request (token is user specific):

.. code-block:: http

    POST /api/project-cloud-memberships/1/set_quotas/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "max_instances": 30,
        "ram": 100000,
        "storage": 1000000,
        "vcpu": 30,
        "security_group_count": 100,
        "security_group_rule_count": 100,
    }

Response code of a successful request is **202 ACCEPTED**. In case link is in a non-stable status, the response would
be **409 CONFLICT**. In this case REST client is advised to repeat the request after some time. On successful
completion the task will synchronize quotas with the backend.

Importing a instance from a project-cloud link
----------------------------------------------

To import an instance with a specific ID from a backend, a person with admin role or staff can issue a POST
request to **/api/project-cloud-memberships/<pk>/import_instances/**. ID of a backend instance has to be in the body
of the request. This request triggers a background instance import task. If it succeeds, a new instance will be created.
Optionally, a URL of an template to be used as a template of a newly created instance can be provided. If the
template is not provided, it is attempted to be derived from the system volume's image metadata.

Example of a valid request (token is user specific):

.. code-block:: http

    POST /api/project-cloud-memberships/1/import_instance/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "id": "c267a5ea-4689-4d10-abdb-f35918125af7",
        "template": "http://example.com/api/iaas-templates/4b3363cf838d4ac7aefde7a0bae8b111/"
    }

If a project-cloud link is in a erred state, operation will return **409 CONFLICT**.
If an instance with a specified backend id already exists, the response will raise **400 BAD REQUEST**.