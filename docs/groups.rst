Groups and permissions
----------------------

NodeConductor is using Django groups for permission management of the higher-level entities like Project or Customer.
Membership in these groups defines if a user account has the corresponding `role <structure.html#project-roles>`__.

Integration with LDAP
+++++++++++++++++++++

It is possible to integrate LDAP with permission group by establishing a synchronisation link between membership
in LDAP groups and in configured Django groups. A typical scenario for that delegation of user membership management
to a single component (LDAP) in the system.

For the moment, it is done by:
- configuring LDAP access from NodeConductor
- creating a new
*nodeconductor.ldapsync.models.LdapToGroup* instance and specifying LDAP group name and the target Django group.
