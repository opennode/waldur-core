VM template is a description of a system installed on VM instances: OS, disk partition etc.

VM template is not to be confused with VM instance flavor -- template is a definition of a system to be installed
(set of software) whereas flavor is a set of virtual hardware parameters.

IaaS Template list
------------------

To get a list of available templates, run GET against **/api/iaas-templates/** as authenticated user.

A user with staff role will be able to see all of the templates, non-staff user only active ones.

An optional filter **?cloud=<CLOUD_UUID>** can be used - if defined, only templates that can be instantiated
on a defined cloud are shown.

In addition, the following filters are supported:

- ?name - case insensitive matching of a template name
- ?os_type - enum matching of an OS type (supported options are: Linux, Windows, Unix, Other).
- ?os - case insensitive matching of a template OS name
- ?type - exact match of the template type
- ?application_type - exact match of the application_type (optional)

IaaS Template permissions
-------------------------

- VM templates are connected to clouds, whereas the template may belong to one cloud only, and the cloud may have
  multiple VM templates.
- Staff members can list all available VM templates in any cloud and create new templates.
- Customer owners can list all VM templates in all the clouds that belong to any of the customers they own.
- Project administrators can list all VM templates and create new VM instances using these templates in all the clouds
  that are connected to any of the projects they are administrators in.
- Project managers can list all VM templates in all the clouds that are connected to any of the projects they are
  managers in.
- Staff members can add licenses to template by sending POST request with list of licenses UUIDs.

Create a new template
---------------------

A new template can only be created by users with staff privilege (is_staff=True). Example of a valid request:

.. code-block:: http

    POST /api/iaas-templates/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "name": "CentOS 7 minimal",
        "description": "Minimal installation of CentOS7",
        "icon_url": "http://centos.org/images/logo_small.png",
        "icon_name": "my_image_stored_in_different_place.png",
        "os": "CentOS 7",
        "os_type": "Linux",
        "is_active": true,
        "sla_level": 99.9,
        "setup_fee": "10",
        "monthly_fee": "20",
        "type": "IaaS",
        "application_type": "OS",
        "template_licenses": [
            "http://example.com:8000/api/template-licenses/5752a31867dc45aebcceafe82c181870/"
        ]
    }


Deletion of a template
----------------------

Deletion of a template is done through sending a DELETE request to the template instance URI.

Valid request example (token is user specific):

.. code-block:: http

    DELETE /api/iaas-templates/33dfe35ecbeb4df0a119c48c206404e9/ HTTP/1.1
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com


Updating a template
-------------------

Can be done by POSTing a new data to the template instance URI, i.e. **/api/template-licenses/<UUID>/**.
