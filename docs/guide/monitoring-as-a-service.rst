Monitoring-as-a-service (MaaS)
==============================

NodeConductor can be used for implementing a MaaS
solution for OpenStack VMs with Zabbix monitoring service.

Two approaches for MaaS are available:

1. A pre-packaged Zabbix appliance deployed into defined OpenStack tenant for
the highest flexibility.

2. A pre-packaged Zabbix appliance configurable by NodeConductor after the
deployment of the appliance ("Advanced monitoring"). Intended for use cases
when OpenStack hosts need to be registered manually or automatically in the
monitoring server deployed in a tenant.

Below we describe configuration approach for both of the cases.

Zabbix appliance only
---------------------

Setup
+++++

1. Create a template group:

  - name, description, icon_url - support parameters for the application store
  - tags - PaaS

2. Add OpenStack Instance template to the template group with the following settings:

  - tags - PaaS
  - service settings - OpenStack settings where a VM needs to be provisioned
  - flavor - default configuration for the created Zabbix server
  - image - OpenStack image with pre-installed Zabbbix
  - data volume, system volume - default size for Zabbix deployments
  - security groups - typically you need to allow at least HTTP and HTTPS traffic

Supported operations by REST client
+++++++++++++++++++++++++++++++++++

Zabbix appliance is a basic OpenStack image that supports the following provisioning
inputs:

 - name
 - project
 - user_data

User data can be used to setup Zabbix admin user password:

.. code-block:: yaml

    #cloud-config
    runcmd:
      - [ bootstrap, -a, <Zabbix admin user password> ]


Advanced monitoring
-------------------

Provisioning flow
+++++++++++++++++

NodeConductor requires a separate template group for advanced monitoring that
contains 2 templates:

- OpenStack VM template - describing provision details of a new VM with Zabbix;

- Zabbix service template - creating a Zabbix service, based on created VM details.


Setup
+++++

1. Create template group:

  - name, description, icon_url - support parameters for the application store 
  - tags - SaaS

2. Add OpenStack instance provision template:

  - tags - SaaS
  - service settings - OpenStack settings where a VM needs to be provisioned
  - flavor - choose suitable for Zabbix image
  - image - OpenStack image with pre-installed Zabbbix
  - data volume, system volume - default size for Zabbix deployments
  - security groups - at least HTTP or HTTPS
  - user data:

  .. code-block:: yaml

      #cloud-config
      runcmd:
        - [ bootstrap, -a, {{ 8|random_password }}, -p, {{ 8|random_password }}, -l, "%", -u, nodeconductor ]


  {{ 8|random_password }} will generate a random password with a length of 8

3. Add Zabbix service provision template:

  - order_number - 2 (should be provisioned after OpenStack VM)
  - name - {{ response.name }} (use VM name for service)
  - Use project of the previous object - True (connect service to VM project)
  - backend url - http://{{ response.access_url.0 }}/zabbix/api_jsonrpc.php (or https)
  - username - Admin
  - password - {{ response.user_data|bootstrap_opts:"a" }}
  - database parameters:

  .. code-block:: json

       {"engine": "django.db.backends.mysql", "name": "zabbix", "host": "localhost(???)", "user": "nodeconductor", 
        "password": "{{ response.user_data|bootstrap_opts:'p' }}", "port": "3306"}


Requests from frontend
++++++++++++++++++++++

1. Creation. Issue post request to template_group provision endpoint with project and name fields.

2. TODO: Describe how to connect instance to host.
