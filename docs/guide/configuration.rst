Configuration
-------------

NodeConductor is a Django_ based application, so configuration is done by modifying settings.py.

If you want to configure options related to Django, such as tune caches, configure custom logging, etc,
please refer to `Django Documentation`_.

Configuration for NodeConductor is namespaced inside a single Django setting, named **NODECONDUCTOR**.

Therefore configuration might look like this:

.. code-block:: python

    NODECONDUCTOR = {
        'OPENSTACK_CREDENTIALS': (
            {
                'auth_url': 'http://keystone.example.com:5000/v2',
                'username': 'node',
                'password': 'conductor',
                'tenant_name': 'admin',
            },
        ),
        'MONITORING': {
            'ZABBIX': {
                'server': "http://zabbix.example.com/zabbix",
                'username': "admin",
                'password': "zabbix",
                'interface_parameters': {"ip": "0.0.0.0", "main": 1, "port": "10050", "type": 1, "useip": 1, "dns": ""},
                'templateid': '10106',
                'default_service_parameters': {'algorithm': 1, 'showsla': 1, 'sortorder': 1, 'goodsla': 95},
            }
        }
    }

Available settings
++++++++++++++++++

.. glossary::

    OPENSTACK_CREDENTIALS
      A list of all known OpenStack deployments.

      Only those OpenStack deployments that are listed here can be managed by NodeConductor.

      Each entry is a dictionary with the following keys:

      auth_url
        Url of the Keystone endpoint including version. Note, that public endpoint is to be used,
        typically it is exposed on port 5000.

      username
        Username of an admin account.
        This used must be able to create tenants within OpenStack.

      password
        Password of an admin account.

      tenant_name
        Name of administrative tenant. Typically this is set to 'admin'.

    MONITORING
      Dictionary of available monitoring engines.

      ZABBIX
        Dictionary of zabbix monitoring engine parameters

          server
            Url of zabbix server

          username
            Username of an zabbix user account.
            This user must be able to create zabbix hostgroups, hosts, templates, service.

          password
            Password of an zabbix user account.

          interface_parameters
            Dictionary of parameters for zabbix hosts interface.
            Have to contain keys: 'main', 'port', 'ip', 'type', 'useip', 'dns'

          templateid
            Id of default zabbix host template.

          default_service_parameters
            Default parameters for zabbix it-services
            Have to contain keys: 'algorithm', 'showsla', 'sortorder', 'goodsla'


.. _Django: https://www.djangoproject.com/
.. _Django Documentation: https://docs.djangoproject.com/en/1.6/
