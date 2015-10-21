SugarCRM service provides an interface to SugarCRM system.
It creates separate VM for each SugarCRM installation via NodeConductor OpenStack endpoints.

SugarCRM services list
----------------------

To get a list of services, run GET against **/api/sugarcrm/** as authenticated user.


Create a SugarCRM service
-------------------------

To create a new SugarCRM service, issue a POST with service details to **/api/sugacrm/** as a customer owner.

Request parameters:

 - name - service name,
 - customer - URL of service customer,
 - settings - URL of SugarCRM settings, if not defined - new settings will be created from server parameters,
 - dummy - is service dummy,

Next parameters will be used for settings creation if settings is not defined:

 - backend_url - URL of OpenStack service project link that will be used for sugarCRM resources creation
                 (required, e.g.: http://example.com/api/openstack-service-project-link/1/);
 - username - NodeConductor user username (e.g. User);
 - password - NodeConductor user password (e.g. Password);
 - image - CRM OpenStack instance image name (default: "sugarcrm");
 - min_ram - minimum amount of ram for CRMs OpenStack instance (default: 2048 MB);
 - min_cores - storage volume size CRMs OpenStack instance. (default: 32768 MB);
 - system_size - storage volume size CRMs OpenStack instance (default: 32768 MB);
 - data_size - data volume size of CRMs OpenStack instance (default: 65536 MB);


Example of a request:


.. code-block:: http

    POST /api/sugarcrm/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "name": "My SugarCRM"
        "customer": "http://example.com/api/customers/2aadad6a4b764661add14dfdda26b373/",
        "backend_url": "http://example.com/",
        "username": "User",
        "password": "Password",
        "image": "SugarCRM-image",
        "backend_spl_id": 13,
    }


Link service to a project
-------------------------
In order to be able to provision SugarCRM resources, it must first be linked to a project. To do that,
POST a connection between project and a service to **/api/sugarcrm-service-project-link/** as stuff user or customer
owner.
For example,

.. code-block:: http

    POST /api/sugarcrm-service-project-link/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "project": "http://example.com/api/projects/e5f973af2eb14d2d8c38d62bcbaccb33/",
        "service": "http://example.com/api/sugarcrm/b0e8a4cbd47c4f9ca01642b7ec033db4/"
    }

To remove a link, issue DELETE to url of the corresponding connection as stuff user or customer owner.


Project-service connection list
-------------------------------
To get a list of connections between a project and an oracle service, run GET against
**/api/sugarcrm-service-project-link/** as authenticated user. Note that a user can only see connections of a project
where a user has a role.


Create new CRM
--------------
CRM - SugarCRM resource. A new CRM can be created by users with project administrator role, customer owner role or with
staff privilege (is_staff=True). To create a CRM, client must issue POST request at **/api/sugarcrm-crms/** with
parameters:

 - name - CRM name;
 - description - CRM description (optional);
 - link to the service-project-link object;


 Example of a valid request:

.. code-block:: http

    POST /api/sugarcrm-crms/ HTTP/1.1
    Content-Type: application/json
    Accept: application/json
    Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
    Host: example.com

    {
        "name": "test CRM",
        "description": "sample description",
        "service_project_link": "http://example.com/api/sugarcrm-service-project-link/1/",
    }


CRM display
-----------

To get CRM data - issue GET request against **/api/sugarcrm-crms/<crm_uuid>/**.

Example rendering of the CRM object:

.. code-block:: javascript

    [
        {
            "url": "http://example.com/api/sugarcrm-crms/7693d9308e0641baa95720d0046e5696/",
            "uuid": "7693d9308e0641baa95720d0046e5696",
            "name": "pavel-test-sugarcrm-11",
            "description": "",
            "start_time": null,
            "service": "http://example.com/api/sugarcrm/655b79490b63442d9264d76ab9478f62/",
            "service_name": "local sugarcrm service",
            "service_uuid": "655b79490b63442d9264d76ab9478f62",
            "project": "http://example.com/api/projects/0e86f04bb1fd48e181742d0598db69d5/",
            "project_name": "local sugarcrm project",
            "project_uuid": "0e86f04bb1fd48e181742d0598db69d5",
            "customer": "http://example.com/api/customers/3b0fc2c0f0ed4f40b26126dc9cbd8f9f/",
            "customer_name": "local sugarcrm customer",
            "customer_native_name": "",
            "customer_abbreviation": "",
            "project_groups": [],
            "resource_type": "SugarCRM.CRM",
            "state": "Provisioning",
            "created": "2015-10-20T10:35:19.146Z"
        }
    ]


Delete CRM
----------

To delete CRM user need to issue DELETE request against **/api/sugarcrm-crms/<crm_uuid>/**.
