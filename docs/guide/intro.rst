Installation
------------

To install NodeConductor standalone on RHEL6-compatible operating systems (CentOS 6, Scientific Linux 6):

.. code-block:: bash

    # Configure repositories
    rpm -Uvh https://dl.fedoraproject.org/pub/epel/6/x86_64/epel-release-6-8.noarch.rpm
    rpm -Uvh https://repos.fedorapeople.org/repos/openstack/openstack-icehouse/rdo-release-icehouse-4.noarch.rpm
    rpm -Uvh http://opennodecloud.com/centos/6/nodeconductor-release.rpm

    # Install and enable services
    yum -y install mysql-server nodeconductor-wsgi redis

    chkconfig httpd on
    chkconfig mysqld on
    chkconfig nodeconductor-celeryd on
    chkconfig redis on

    # Start MySQL and Redis
    service mysqld start
    service redis start

    # Create MySQL database
    mysql -e "CREATE DATABASE nodeconductor CHARACTER SET = utf8;"
    mysql -e "CREATE USER 'nodeconductor'@'localhost' IDENTIFIED BY 'nodeconductor';"
    mysql -e "GRANT ALL PRIVILEGES ON nodeconductor.* to 'nodeconductor'@'localhost';"

    # Init NodeConductor database and collect static data
    nodeconductor syncdb --noinput
    nodeconductor migrate --noinput
    nodeconductor collectstatic --noinput
    chown -R nodeconductor:nodeconductor /var/log/nodeconductor

    # (optional) Create data structures and populate database with randomly generated sample data
    nodeconductor createsampledata alice
    nodeconductor createsampledata random

    # Start Celery and Apache
    service nodeconductor-celeryd start
    service httpd start

All done. NodeConductor API should be available at http://myserver/api/ (port 80).

Note that MySQL and Redis may run on a separate servers -- in this case modify installation process accordingly.

Upgrade
+++++++

TODO

.. include:: configuration.rst
.. include:: background.rst
.. include:: fsm.rst
.. include:: structure.rst
.. include:: groups.rst
.. include:: license.rst
