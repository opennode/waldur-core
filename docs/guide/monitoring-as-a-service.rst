Monitoring as a service
=======================

Monitoring is offered on two levels:

1. As PaaS service - packaging monitoring server and deploying into customer's tenant for the highest flexibility. 
2. As an 'Advanced monitoring' extension of the Self-service, where configuration of the monitoring system is done in 
assisted form and monitoring data is partially integrated into a self-service portal. The service is for IaaS VMs only.


Monitoring as PaaS service
--------------------------

Setup
+++++

1. Create template group:

  - name, description, icon_url - AppStore parameters
  - tags - PaaS

2. To created group add OpenStack instance provision template:

  - tags - PaaS
  - service settings - share OpenStack settings
  - flavor - choose suitable for Zabbix image
  - image - Zabbix image
  - data volume, system volume - suitable for Zabbix image
  - security groups - at least http or https


Requests from frontend
++++++++++++++++++++++

Monitoring as PaaS should be threated as any other PaaS service - it has separate security group with tag "PaaS" and 
receives specific user-data.
Parameters for provision:

 - name
 - project
 - user_data

User data format:

.. code-block:: yaml

    #cloud-config
    runcmd:
      - [ bootstrap, -a, <Zabbix Admin user password> ]


Advanced monitoring
-------------------

How it works in NC
++++++++++++++++++

NC has separate template group for advance monitoring that contains 2 templates:

 - OpenStack VM template - describes provision details, creates new VM with Zabbix.
 - Zabbix service template - creates Zabbix service, based on created VM details.


Setup
+++++

1. Create template group:

  - name, description, icon_url - AppStore parameters.
  - tags - SaaS

2. Add OpenStack instance provision template:

  - tags - SaaS
  - service settings - shared OpenStack settings
  - flavor - choose suitable for Zabbix image
  - image - Zabbix image
  - data volume, system volume - suitable for Zabbix image
  - security groups - at least http or https
  - user data ({{ 8|random_password }} - generates random password):

  .. code-block:: yaml

      #cloud-config
      runcmd:
        - [ bootstrap, -a, {{ 8|random_password }}, -p, {{ 8|random_password }}, -l, "%", -u, nodeconductor ]

3. Add Zabbix service provision template:

  - order_number - 2 (should be provisioned right after OpenStack VM)
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