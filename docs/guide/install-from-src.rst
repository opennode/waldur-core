Installation from source
------------------------

Additional requirements:

- ``git``
- ``virtualenv``
- C compiler and development libraries needed to build dependencies

  - CentOS: ``gcc libffi-devel openssl-devel``
  - Ubuntu: ``gcc libffi-dev libsasl2-dev libssl-dev python-dev``

**NodeConductor installation**

1. Get the code:

  .. code-block:: bash

    git clone https://github.com/opennode/nodeconductor.git

2. Create a Virtualenv and update Setuptools:

  .. code-block:: bash

    cd nodeconductor
    virtualenv venv
    venv/bin/pip install --upgrade setuptools

3. Install NodeConductor in development mode along with dependencies:

  .. code-block:: bash

    venv/bin/python setup.py develop

4. Create and edit settings file (see 'Configuration' section for details):

  .. code-block:: bash

    cp nodeconductor/server/settings.py.example nodeconductor/server/settings.py
    vi nodeconductor/server/settings.py

5. Initialise database -- SQLite3 database will be created in ``./db.sqlite3`` unless specified otherwise in settings files:

  .. code-block:: bash

    venv/bin/nodeconductor migrate --noinput

6. Collect static data -- static files will be copied to ``./static/`` in the same directory:

  .. code-block:: bash

    venv/bin/nodeconductor collectstatic --noinput

7. In order to install SAML2_ based authentication you should also install ``nodeconductor-saml2`` plugin.

8. Start NodeConductor:

  .. code-block:: bash

    venv/bin/nodeconductor runserver

Configuration
+++++++++++++

NodeConductor is a Django_ based application, so configuration is done by modifying settings.py.

If you want to configure options related to Django, such as tune caches, configure custom logging, etc,
please refer to `Django documentation`_.

Configuration for NodeConductor is namespaced inside a single Django setting, named **NODECONDUCTOR**.

Therefore configuration might look like this:

.. code-block:: python

    NODECONDUCTOR = {
        'EXTENSIONS_AUTOREGISTER': True,
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
                'FAIL_SILENTLY': True,
                'HISTORY_RECORDS_INTERVAL': 60,
                'TRENDS_RECORDS_INTERVAL': 60,
                'HISTORY_DATE_RANGE': 48,
                # application-specific templates
                'wordpress-templateid': '10107',
                'zimbra-templateid': '10108',
                'postgresql-templateid': '10109',
                'application-status-item': 'application.status',
            }
        },
        'OPENSTACK_QUOTAS_INSTANCE_RATIOS': {
            'volumes': 4,
            'snapshots': 20,
        },
    }

**Available settings**

.. glossary::

    CLOSED_ALERTS_LIFETIME
      Specifies closed alerts lifetime (timedelta value, for example timedelta(hours=1)).
      Expired closed alerts will be removed during the cleanup.

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

    ELASTICSEARCH
      Dictionary of Elasticsearch parameters.

        host
          Elasticsearch host (string).

        port
          Elasticsearch port (integer).

        protocol
          Elasticsearch server access protocol (string).

        username
          Username for accessing Elasticsearch server (string).

        password
          Password for accessing Elasticsearch server (string).

        verify_certs
          Enables verification of Elasticsearch server TLS certificates (boolean).

        ca_certs
          Path to the TLS certificate bundle (string).

    ENABLE_GEOIP
      Indicates whether geolocation is enabled (boolean).

    EXTENSIONS_AUTOREGISTER
      Defines whether extensions should be automatically registered (boolean).

    GOOGLE_API
      Settings dictionary for Google Cloud Messaging.

        Android
          Settings for Android devices.

            project_id
              Google Cloud messaging project ID.

            server_key
              Google Cloud messaging server key.

        IOS
          Settings for IOS devices.

            project_id
              Google Cloud messaging project ID.

            server_key
              Google Cloud messaging server key.

    MONITORING
      Dictionary of available monitoring engines.

      ZABBIX
        Dictionary of Zabbix monitoring engine parameters.

          server
            URL of Zabbix server (string).

          username
            Username of Zabbix user account (string).
            This user must be able to create zabbix hostgroups, hosts, templates and IT services.

          password
            Password of Zabbix user account (string).

          interface_parameters
            Dictionary of parameters for Zabbix hosts interface.
            Have to contain keys: 'main', 'port', 'ip', 'type', 'useip', 'dns'.

          templateid
            Id of default Zabbix host template (string).

          groupid
            Id of default Zabbix host group (string).

          default_service_parameters
            Dictionary of default parameters for Zabbix IT services.
            Have to contain keys: 'algorithm', 'showsla', 'sortorder', 'goodsla'.

          FAIL_SILENTLY
            If True - ignores Zabbix API exceptions and do not add any messages to logger (boolean).

          HISTORY_RECORDS_INTERVAL
            The time for maximal interval between history usage records in Zabbix (number of minutes).

          TRENDS_RECORDS_INTERVAL
            The time for maximal interval between trends usage records in Zabbix (number of minutes).

          HISTORY_DATE_RANGE
            The time interval on which Zabbix will use records from history table (number of hours).

          There could be also application-specific parameters specified:
            For example, wordpress-templateid, zimbra-templateid,
            postgresql-templateid, application-status-item.

    SHOW_ALL_USERS
      Indicates whether user can see all other users in `api/users/` endpoint (boolean).

    SUSPEND_UNPAID_CUSTOMERS
      If it is set to True, then only customers with positive balance will be able
      to modify entities such as services and resources (boolean).

    OPENSTACK_QUOTAS_INSTANCE_RATIOS
      Dictionary of default ratio values per instance.

        volumes
          Number of volumes per instance.

        snapshots
          Number of snapshots per instance.

    OWNER_CAN_MANAGE_CUSTOMER
      Indicates whether user who has owner role in customer can manage it (boolean).

    TOKEN_KEY
      Header for token authentication. For example, 'x-auth-token'.

    TOKEN_LIFETIME
      Specifies authentication token lifetime (timedelta value, for example timedelta(hours=1)).


NodeConductor will send notifications from email address specified in **DEFAULT_FROM_EMAIL** variable.
For example,

.. code-block:: python

    DEFAULT_FROM_EMAIL='noreply@example.com'


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
