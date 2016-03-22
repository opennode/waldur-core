Installation from RPM repository
--------------------------------

To install NodeConductor standalone on RHEL7-compatible operating systems (CentOS 7, Scientific Linux 7):

.. literalinclude:: bootstrap-centos7.sh
   :language: bash

All done. NodeConductor API should be available at http://myserver/api/ (port 80).

Note that MySQL and Redis may run on a separate servers -- in this case modify installation process accordingly.

For plugin installation instructions see NodeConductor's plugin `section <../index.html#nodeconductor-plugins>`_.

Configuration
+++++++++++++

NodeConductor configuration file can be found at ``/etc/nodeconductor/settings.ini``.
