Welcome to NodeConductor's documentation!
=========================================

NodeConductor is a RESTful server for management of IT infrastructure. It uses a project-based approach for
separation of managed resources (VMs, subnets, applications and more).

Features include:

- flexible user, group and project management;
- delegation of privileges natural for enterprise setups: owners, managers and administrators;
- support for multiple IaaS back-ends;
- support for billing;
- support for license management;
- support for SLA tracking.

Guide
-----

.. toctree::
   :maxdepth: 1

   changelog
   guide/intro


API
---

.. toctree::
   :maxdepth: 1

   drfapi/index

IAAS
----

.. toctree::
   :maxdepth: 1

   api/api

NodeConductor plugins
---------------------

.. toctree::
   :maxdepth: 1

   plugins/azure
   plugins/jira
   plugins/killbill
   plugins/openstack
   plugins/oracle
   plugins/organization
   plugins/paypal
   plugins/saltstack
   plugins/saml2
   plugins/sugarcrm
   plugins/zabbix

Developing NodeConductor
------------------------

.. toctree::
   :maxdepth: 1

   developer/developer
   developer/sample-data


License
-------

NodeConductor is open-source under MIT license.


Indices and tables
==================

* :ref:`genindex`
* :ref:`search`
