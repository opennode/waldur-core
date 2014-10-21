Installation
------------

To install NodeConductor on RHEL6-compatible operating systems (CentOS6, Scientific Linux 6):

.. code-block:: bash

    curl http://opennodecloud.com/CentOS/6/nodeconductor/nodeconductor.repo > /etc/yum.repos.d/nodeconductor.repo
    rpm --import http://opennodecloud.com/CentOS/6/nodeconductor/RPM-GPG-KEY-ActiveSys
    # some dependency are taken from EPEL repository
    rpm -Uvh http://download.fedoraproject.org/pub/epel/6/i386/epel-release-6-8.noarch.rpm

    # to serve via apache httpd
    yum install nodeconductor-wsgi

    # to run as standalone (dev/test)
    yum install nodeconductor

.. include:: structure.rst
.. include:: groups.rst
.. include:: license.rst
