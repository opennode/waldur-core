Zabbix
======

Zabbix plugin provides an interface to Zabbix monitoring system.

Read more about `Zabbix plugin <http://nodeconductor-zabbix.readthedocs.org/en/stable/>`_.

Installation from RPM repository
--------------------------------

1. Install NodeConductor as described `here <http://nodeconductor.readthedocs.org/en/stable/guide/intro.html#installation-from-rpm-repository>`_.
2. Install plugin:

.. code-block:: bash

    yum install nodeconductor-zabbix

    # Migrate NodeConductor database
    nodeconductor migrate --noinput
    chown -R nodeconductor:nodeconductor /var/log/nodeconductor

    # Restart Celery and Apache
    systemctl restart httpd
    systemctl restart nodeconductor-celery
    systemctl restart nodeconductor-celerybeat
