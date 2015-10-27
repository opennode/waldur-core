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

4. Create and edit settings file:

  .. code-block:: bash

    cp nodeconductor/server/settings.py.example nodeconductor/server/settings.py
    vim nodeconductor/server/settings.py

5. Initialise database -- SQLite3 database will be created in ``./db.sqlite3`` unless specified otherwise in settings files:

  .. code-block:: bash

    venv/bin/nodeconductor migrate --noinput

6. Collect static data -- static files will be copied to ``./static/`` in the same directory:

  .. code-block:: bash

    venv/bin/nodeconductor collectstatic --noinput

7. In order to install SAML2_ based authentication you should also install ``nodeconductor-saml2`` plugin.

Configuration
+++++++++++++

NodeConductor is a Django_ based application, so configuration is done by modifying settings.py.

If you want to configure options related to Django, such as tune caches, configure custom logging, etc,
please refer to `Django documentation`_.

Configuration for NodeConductor is namespaced inside a single Django setting, named **NODECONDUCTOR**.

Therefore configuration might look like this:

.. code-block:: python

    NODECONDUCTOR = {
        'DEFAULT_SECURITY_GROUPS': (
            {
                'name': 'ssh',
                'description': 'Security group for secure shell access',
                'rules': (
                    {
                        'protocol': 'tcp',
                        'cidr': '0.0.0.0/0',
                        'from_port': 22,
                        'to_port': 22,
                    },
                    {
                        'protocol': 'icmp',
                        'cidr': '0.0.0.0/0',
                        'icmp_type': -1,
                        'icmp_code': -1,
                    },
                ),
            },
        ),
        'MONITORING': {
            'ZABBIX': {
                'server': 'http://zabbix.example.com/zabbix',
                'username': 'admin',
                'password': 'zabbix',
                'interface_parameters': {'ip': '0.0.0.0', 'main': 1, 'port': '10050', 'type': 1, 'useip': 1, 'dns': ''},
                'templateid': '10106',
                'groupid': '8',
                'default_service_parameters': {'algorithm': 1, 'showsla': 1, 'sortorder': 1, 'goodsla': 95},
            }
        }
        'OPENSTACK_QUOTAS_INSTANCE_RATIOS': {
            'volumes': 4,
            'snapshots': 20,
        },
        'BILLING': {
            'backend': 'nodeconductor.billing.backend.killbill.KillBillAPI',
            'api_url': 'http://killbill.example.com/1.0/kb/',
            'username': 'admin',
            'password': 'password',
            'api_key': 'bob',
            'api_secret': 'lazar',
            'currency': 'USD',
        }
    }

**Available settings**

.. glossary::

    DEFAULT_SECURITY_GROUPS
      A list of security groups that will be created in IaaS backend for each cloud.

      Each entry is a dictionary with the following keys:

      name
        Short name of the security group.

      description
        Detailed description of the security group.

      rules
        List of firewall rules that make up the security group.

        Each entry is a dictionary with the following keys:

        protocol
          Transport layer protocol the rule applies to.
          Must be one of *tcp*, *udp* or *icmp*.

        cidr
          IPv4 network of packet source.
          Must be a string in `CIDR notation`_.

        from_port
          Start of packet destination port range.
          Must be a number in range from 1 to 65535.

          For *tcp* and *udp* protocols only.

        to_port
          End of packet destination port range.
          Must be a number in range from 1 to 65535.
          Must not be less than **from_port**.

          For *tcp* and *udp* protocols only.

        icmp_type
          ICMP type of the packet.
          Must be a number in range from -1 to 255.

          See also: `ICMP Types and Codes`_.

          For *icmp* protocol only.

        icmp_code
          ICMP code of the packet.
          Must be a number in range from -1 to 255.

          See also: `ICMP Types and Codes`_.

          For *icmp* protocol only.

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

          FAIL_SILENTLY
            If True - ignores Zabbix API exceptions and do not add any messages to logger

    OPENSTACK_QUOTAS_INSTANCE_RATIOS
      Default ratio values per instance.

        volumes
          Number of volumes per instance.

        snapshots
          Number of snapshots per instance.

    BILLING
      Dictionary of billing engine parameters.

        backend
          Path to Kill Bill driver.

        api_url
          Url of Kill Bill API.

        username
            Username of Kill Bill admin account.

        password
            Password of Kill Bill admin account.

        api_key
            Kill Bill tenant API key.

        api_secret
            Kill Bill tenant API secret.

        Additional Kill Bill parameters. For example: **currency**.


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
.. _ICMP Types and Codes: http://en.wikipedia.org/wiki/Internet_Control_Message_Protocol#Control_messages
.. _CIDR notation: http://en.wikipedia.org/wiki/Classless_Inter-Domain_Routing#CIDR_notation
.. _SAML2: https://en.wikipedia.org/wiki/SAML_2.0
