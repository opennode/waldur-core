Installation from RPM repository
--------------------------------

To install NodeConductor standalone on RHEL6-compatible operating systems (CentOS 6, Scientific Linux 6):

.. literalinclude:: bootstrap.sh
   :language: bash

All done. NodeConductor API should be available at http://myserver/api/ (port 80).

Note that MySQL and Redis may run on a separate servers -- in this case modify installation process accordingly.

Configuration
+++++++++++++

NodeConductor configuration file can be found at ``/etc/nodeconductor/settings.ini``.

Example configuration file (this is already included in your installation): `settings.ini example`_

.. _settings.ini example: settings-ini-example.html
