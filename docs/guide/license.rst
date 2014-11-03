License management
------------------

Every Template is connected to one or more consumed licenses. License is defined as an abstract consumable - e.g. an
OS license or application license. NodeConductor offers a generic support for license management,
exact configuration/interpretation is left for configuration.

There are two main concepts:

- Template license - connected to a concrete license;
- Instance license - connected to a concrete IaaS instance.

When a new instance is created from a template, all licenses are cloned to the instance. This allows to edit template
licenses without affecting existing VMs.

License instance
++++++++++++++++
Each license can have a type defined by the enum in DB.
Each license supports fees in currency fields: one-time free and monthly fee.


Permissions
+++++++++++
Staff user can create licenses and link them to templates.

Customer owner, project admin and manager can query information about license instances connected with vm instances and
templates.

Summary queries
+++++++++++++++

It is possible to issue queries to NodeConductor to get aggregate statistics about consumed instance licenses. Queries
can be run by all users with a answers scoped by their visibility permissions for instances. Please see API section for
more details.

Supported aggregate queries include:

- by project names;
- by project groups;
- by license type.
