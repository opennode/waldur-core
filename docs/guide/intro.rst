Installation
------------

To install NodeConductor on RHEL6-compatible operating systems (CentOS 6, Scientific Linux 6):

.. code-block:: bash

    curl http://opennodecloud.com/CentOS/6/nodeconductor.repo > /etc/yum.repos.d/nodeconductor.repo
    rpm --import http://opennodecloud.com/CentOS/6/RPM-GPG-KEY-ActiveSys

    # Some dependencies are taken from EPEL repository
    rpm -Uvh http://download.fedoraproject.org/pub/epel/6/i386/epel-release-6-8.noarch.rpm

    # To serve via WSGI using Apache HTTPd (recommended for production environments)
    yum install nodeconductor-wsgi

    # To run standalone (recommended for development environments)
    yum install nodeconductor

.. include:: background.rst
.. include:: fsm.rst
.. include:: structure.rst
.. include:: groups.rst
.. include:: license.rst
