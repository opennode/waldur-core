Setting a project-cloud link quota
----------------------------------

A project quota can be set within for a particular link between cloud and project by users with staff privilege.
Setting the quota requires that the resource corresponding to the link would be created. To set a quota, submit
POST request to **/api/project-cloud-memberships/<pk>/set_quotas/**. The quota values are propagated to the backend.

The following is a list of supported quotas. All values are expected to be integers:

- max_instance - maximal number of created instances.
- ram - maximal size of ram for allocation. In MiB_.
- storage - maximal size of storage for allocation. In MiB_.
- vcpu - maximal number of virtual cores for allocation.

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
        "vcpu": 30
    }

If a request was successful, response code will be **202**. In case link is in a non-stable status, the response would
be **409**. In this case REST client is advised to repeat the request after some time. On successful completion, the
task will synchronize quotas with a backend.

Getting project quota and usage
-------------------------------

To get an actual value for project quotas and project usage issue a GET request against **/api/projects/**.

Example of a valid response:

.. code-block:: http

    GET /api/projects/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com
    {
        ...
        "name": "Project A",
        "resource_quota": {
            "vcpu": 26,
            "ram": 229.0,
            "storage": 124.0,
            "max_instances": 199
        },
        "resource_quota_usage": {
            "vcpu": 22,
            "ram": 225.0,
            "storage": 113.0,
            "max_instances": 186
        },
        ...
    }