SAML2
=====

SAML2 plugin implements SAML2 consumer for authentication.

Read more about `SAML2 plugin <http://nodeconductor-saml2.readthedocs.org/en/stable/>`_.

Installation from RPM repository
--------------------------------

1. Install NodeConductor as described `here <http://nodeconductor.readthedocs.org/en/stable/guide/intro.html#installation-from-rpm-repository>`_.
2. Install plugin:

.. code-block:: bash

    yum install nodeconductor-saml2

    # Migrate NodeConductor database
    nodeconductor migrate --noinput
    chown -R nodeconductor:nodeconductor /var/log/nodeconductor

    # Restart Celery and Apache
    systemctl restart httpd
    systemctl restart nodeconductor-celery
    systemctl restart nodeconductor-celerybeat
