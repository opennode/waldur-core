Installation from source
------------------------

Additional requirements:

- ``git``
- ``redis`` and ``hiredis`` library
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
        'CLOSED_ALERTS_LIFETIME': timedelta(weeks=1),
        'ELASTICSEARCH': {
            'username': 'username',
            'password': 'password',
            'host': 'example.com',
            'port': '9999',
            'protocol': 'https',
        },
        'ENABLE_GEOIP': True,
        'EXTENSIONS_AUTOREGISTER': True,
        'GOOGLE_API': {
            'Android': {
                'server_key': 'AIzaSyA2_7UaVIxXfKeFvxTjQNZbrzkXG9OTCkg',
            },
            'iOS': {
                'server_key': 'AIzaSyA34zlG_y5uHOe2FmcJKwfk2vG-3RW05vk',
            }
        },
        'SHOW_ALL_USERS': False,
        'SUSPEND_UNPAID_CUSTOMERS': False,
        'OWNER_CAN_MANAGE_CUSTOMER': False,
        'TOKEN_KEY': 'x-auth-token',
        'TOKEN_LIFETIME': timedelta(hours=1),
    }

**Available settings**

.. glossary::

    CLOSED_ALERTS_LIFETIME
      Specifies closed alerts lifetime (timedelta value, for example timedelta(hours=1)).
      Expired closed alerts will be removed during the cleanup.

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

            server_key
              Google Cloud messaging server key.

        IOS
          Settings for IOS devices.

            server_key
              Google Cloud messaging server key.

        NOTIFICATION_TITLE
           String to be displayed in the notification pop-up title.

    SELLER_COUNTRY_CODE
      Seller legal or effective country of registration or residence as an ISO 3166-1 alpha-2 country code.
      It is used for computing VAT charge rate.

    SHOW_ALL_USERS
      Indicates whether user can see all other users in `api/users/` endpoint (boolean).

    SUSPEND_UNPAID_CUSTOMERS
      If it is set to True, then only customers with positive balance will be able
      to modify entities such as services and resources (boolean).

    OWNER_CAN_MANAGE_CUSTOMER
      Indicates whether user can manage owned customers (boolean).

    TOKEN_KEY
      Header for token authentication. For example, 'x-auth-token'.

    TOKEN_LIFETIME
      Specifies authentication token lifetime (timedelta value, for example timedelta(hours=1)).


NodeConductor will send notifications from email address specified in **DEFAULT_FROM_EMAIL** variable.
For example,

.. code-block:: python

    DEFAULT_FROM_EMAIL='noreply@example.com'

See also: `Django database settings`_.

.. _Django: https://www.djangoproject.com/
.. _Django documentation: https://docs.djangoproject.com/en/1.8/
.. _Django database settings: https://docs.djangoproject.com/en/1.8/ref/settings/#databases
.. _ICMP Types and Codes: http://en.wikipedia.org/wiki/Internet_Control_Message_Protocol#Control_messages
.. _CIDR notation: http://en.wikipedia.org/wiki/Classless_Inter-Domain_Routing#CIDR_notation
.. _SAML2: https://en.wikipedia.org/wiki/SAML_2.0
