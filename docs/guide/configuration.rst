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



.. _Django: https://www.djangoproject.com/
.. _Django Documentation: https://docs.djangoproject.com/en/1.6/
