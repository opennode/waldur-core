Listing structure permission
----------------------------

Structure is an entity defining organisational relationship. Currently supported are 3 structures:

- customer: endpoint **/api/customer-permissions/**
- project_group: endpoint **/api/project-groups-permissions/**
- project: endpoint **/api/project-permissions/**

Each structure has a list of users associated with it with roles.
Getting a list of users connected to a certain structure is done through running a GET request against
the corresponding endpoint.

Filtering by structure UUID is supported, depending on the structure filter field is one of:

- ?customer=<UUID>
- ?project_group=<UUID>
- ?project=<UUID>

Ordering can be done by setting an ordering field with **?o=<field_name>**. For descending ordering prefix field name
with **-**. Supported field names are:

- ?o=user__username
- ?o=user__full_name
- ?o=user__native_name

