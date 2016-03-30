SugarCRM
========

SugarCRM service provides an interface to SugarCRM system.
It creates separate VM for each SugarCRM installation via NodeConductor OpenStack endpoints.

Read more about `SugarCRM plugin <http://nodeconductor-sugarcrm.readthedocs.org/en/stable/>`_.

Installation from RPM repository
--------------------------------

1. Install NodeConductor as described `here <http://nodeconductor.readthedocs.org/en/stable/guide/intro.html#installation-from-rpm-repository>`_.
2. Install plugin:

.. code-block:: bash

    yum install nodeconductor-sugarcrm

    # Migrate NodeConductor database
    nodeconductor migrate --noinput
    chown -R nodeconductor:nodeconductor /var/log/nodeconductor

    # Restart Celery and Apache
    systemctl restart httpd
    systemctl restart nodeconductor-celery
    systemctl restart nodeconductor-celerybeat
