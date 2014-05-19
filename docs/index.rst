Welcome to NodeConductor's documentation!
=========================================

NodeConductor is a RESTful server for management of the IT infrastructure based on the concept
of configuration management.

Motivation
----------

Configuration management is a great way to describe and implement best practices for deployment and lifecycle
management of the applications. However, for multitenant cases when we have multiple environments,
with potentially different lifecycles, maintaining a single set of configuration management scrips becomes too
restrictive. NodeConductor aims at simplifying this by providing a system for management of the shared
configuration formulas.

Example use cases
-----------------

TBA


Main concepts
-------------

Template
  A configuration management formula. Contains a state description and a set of example variables.
  
Application
  Instantiated and deployment specific instance of the template.

Environment
  collection of Applications.


Configuration repository structure
----------------------------------

- Template - central store shared by all environments.
- Application instance - forked repository of a formula.
- Environment - a group containing Application instance repositories.

Connections
-----------


.. toctree::
   :maxdepth: 2




Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

