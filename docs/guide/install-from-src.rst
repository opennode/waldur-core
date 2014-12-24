Installation from source
------------------------

Additional requirements:

- ``git``
- ``virtualenv``
- C compiler and development libraries needed to build dependencies

  - CentOS: ``gcc libffi-devel openldap-devel openssl-devel python-devel``
  - Ubuntu: ``gcc libffi-dev libldap2-dev libsasl2-dev libssl-dev python-dev``

**NodeConductor installation**

1. Get the code:

  .. code-block:: bash

    git clone https://github.com/opennode/nodeconductor.git

2. Create a virtualenv:

  .. code-block:: bash

    cd nodeconductor
    virtualenv venv

3. Install nodeconductor in development mode along with dependencies:

  .. code-block:: bash

    venv/bin/python setup.py develop

4. Create settings file -- settings files will be created in ``~/.nodeconductor`` directory:

  .. code-block:: bash

    venv/bin/nodeconductor init

5. Initialise database -- SQLite3 database will be created in ``~/.nodeconductor/db.sqlite`` unless specified otherwise in settings files:

  .. code-block:: bash

    venv/bin/nodeconductor syncdb --noinput
    venv/bin/nodeconductor migrate --noinput

6. Collect static data -- static files will be copied to ``static_files`` in the same directory:

  .. code-block:: bash

    venv/bin/nodeconductor collectstatic --noinput

Configuration
+++++++++++++

NodeConductor is a Django_ based application, so configuration is done by modifying settings.py.

If you want to configure options related to Django, such as tune caches, configure custom logging, etc,
please refer to `Django documentation`_.

Configuration for NodeConductor is namespaced inside a single Django setting, named **NODECONDUCTOR**.

Therefore configuration might look like this:

.. code-block:: python

    NODECONDUCTOR = {
        'OPENSTACK_CREDENTIALS': (
            {
                'auth_url': 'http://keystone.example.com:5000/v2.0',
                'username': 'node',
                'password': 'conductor',
                'tenant_name': 'admin',
            },
        ),
        'MONITORING': {
            'ZABBIX': {
                'server': 'http://zabbix.example.com/zabbix',
                'username': 'admin',
                'password': 'zabbix',
                'interface_parameters': {'ip': '0.0.0.0', 'main': 1, 'port': '10050', 'type': 1, 'useip': 1, 'dns': ''},
                'templateid': '10106',
                'templateid': '42',
                'default_service_parameters': {'algorithm': 1, 'showsla': 1, 'sortorder': 1, 'goodsla': 95},
            }
        }
    }

**Available settings**

.. glossary::

    OPENSTACK_CREDENTIALS
      A list of all known OpenStack deployments.

      Only those OpenStack deployments that are listed here can be managed by NodeConductor.

      Each entry is a dictionary with the following keys:

      auth_url
        URL of the Keystone endpoint including version. Note, that public endpoint is to be used,
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
        Dictionary of Zabbix monitoring engine parameters.

          server
            URL of Zabbix server.

          username
            Username of Zabbix user account.
            This user must be able to create zabbix hostgroups, hosts, templates and IT services.

          password
            Password of Zabbix user account.

          interface_parameters
            Dictionary of parameters for Zabbix hosts interface.
            Have to contain keys: 'main', 'port', 'ip', 'type', 'useip', 'dns'.

          templateid
            Id of default Zabbix host template.

          groupid
            Id of default Zabbix host group.

          default_service_parameters
            Default parameters for Zabbix IT services.
            Have to contain keys: 'algorithm', 'showsla', 'sortorder', 'goodsla'.

NodeConductor also needs access to Zabbix database. For that a read-only user needs to be created in Zabbix database.

Zabbix database connection is configured as follows:

.. code-block:: python

    DATABASES = {
        'zabbix': {
            'ENGINE': 'django.db.backends.mysql',
            'HOST': 'zabbix_db_host',
            'NAME': 'zabbix_db_name',
            'PORT': 'zabbix_db_port',
            'USER': 'zabbix_db_user',
            'PASSWORD': 'zabbix_db_password',
        }
    }

.. glossary::

    zabbix_db_host
      Hostname of the Zabbix database.

    zabbix_db_port
      Port of the Zabbix database.

    zabbix_db_name
      Zabbix database name.

    zabbix_db_user
      User for connecting to Zabbix database.

    zabbix_db_password
      Password for connecting to Zabbix database.

See also: `Django database settings`_.

.. _Django: https://www.djangoproject.com/
.. _Django documentation: https://docs.djangoproject.com/en/1.6/
.. _Django database settings: https://docs.djangoproject.com/en/1.7/ref/settings/#databases
