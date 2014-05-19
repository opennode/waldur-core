Welcome to NodeConductor's documentation!
=========================================

NodeConductor is a RESTful server for management of the IT infrastructure based on the concept
of configuration management.

Motivation
----------

Configuration management is a great way to describe and implement best practices for deployment and lifecycle
management of the applications. However, for multitenant cases when we have multiple environments,
with potentially different lifecycles, maintaining a single set of configuration management scrips becomes too
restrictive. Moreover, we don't want to depend on upstream as it might be down, decide to introduce destructive
changes or do something equally evil. 

NodeConductor aims at solcing this issue by providing a system for management of the shared
configuration formulas.

Main concepts
-------------

Template
  A configuration management formula. Contains a state description and a set of example variables. A Template corresponds
  to a "correct way" of handling an certain component, e.g. MySQL DB or Liferay portal.

Host
  A virtual or physical machine where application is running. Host is used for targeting by the configuration management
  system.

Application
  Instantiated and deployment specific instance of the template.

Environment
  Collection of Applications.


Configuration repository structure
----------------------------------

- **Template** - central store shared by all environments.
- **Application component** - forked repository of a formula.
- **Orchestration** - an 'overstate' binding together hosts and application's component.
- **Environment** - a group containing Application instance repositories.


Example structure
-----------------

Input data:

- **Client:** Elvis P.
- **Application:** Django-based e-commerce "MyTunes"
- **Environment:** Staging

Results in the logical structure.

**/elvisp (group)**
  A client specific area.

**/elvisp/mytunes (group)**
  Application specific area.

**/elvisp/mytunes/stg (group)**
  Staging environment of the application.

**/elvisp/mytunes/stg/mysql-formula**
  Fork of the upstream mysql-formula.
  
**/elvisp/mytunes/stg/django-formula**
  Fork of upstream django-formula.

**/elvisp/mytunes/stg/mytunes-orchestration**
  Orchestration and targeting for the staging environment of "MyTunes".

**/elvisp/mytunes/stg/mytunes-pillar**
  A standalone repository containing sensitive data - passwords, keys, etc.


.. toctree::
   :maxdepth: 2


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

