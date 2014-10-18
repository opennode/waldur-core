License management
------------------

Every template is potential connected to one or more consumed licenses. LicenseTemplate is defined as an abstract consumable.
NC offers a generic support for license management, exact configuration/interpretation is left for configuration.

License instance
++++++++++++++++
Each license can have a type defined by the enum in DB.
Each license supports fees in currency fields: one-time free and monthly fee.

When a VM instance is created from a template, corresponing license instances are created and connected with Instance.


Permissions
+++++++++++
Staff user can create licenses and link them to templates.

Customer owner, project admin and manager can information about license instances connected with vm instances and
templates.

Summary queries
+++++++++++++++

It is possible to issue queries to NC to get aggregate statistics about consumed licenses.
Query is done against **/licenses/stats/** endpoint. Queries can be run by all users with a answers scoped
by their visibility permissions for instances.

Supported aggregate queries are:

- by project names;
- by project groups;
- by license type.
