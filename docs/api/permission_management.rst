Listing permissions
-------------------

Entities of NodeConductor are grouped into *organisational units*.
The following *organisational units* are supported: customer, project group and project.

Each *organisational unit* has a list of users associated with it.
Getting a list of users connected to a certain *organisational unit* is done through running a
GET request against a corresponding endpoint.

- customer: endpoint **/api/customer-permissions/**
- project_group: endpoint **/api/project-group-permissions/**
- project: endpoint **/api/project-permissions/**

Filtering by *organisational unit* UUID is supported. Depending on the type, filter field is one of:

- ?customer=<UUID>
- ?project_group=<UUID>
- ?project=<UUID>

Ordering can be done by setting an ordering field with **?o=<field_name>**. For descending ordering prefix field name
with a dash (-). Supported field names are:

- ?o=user__username
- ?o=user__full_name
- ?o=user__native_name
