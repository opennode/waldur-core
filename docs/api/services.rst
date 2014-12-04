Services list
-------------

Use */api/services/* to get a list of all the service that a user can see.

Supported filters are:

- ?hostname - case insensitive matching of a hostname
- ?service_name - case insensitive matching of a service name
- ?customer_name - case insensitive matching of a customer name
- ?project_name - case insensitive matching of a project name
- ?project_groups - case insensitive matching of a project_group name
- ?agreed_sla - exact match of SLA numbers
- ?actual_sla - exact match of SLA numbers

Ordering can be done by the following fields (prefix with **-** for descending order):

- ?o=hostname
- ?o=template__name
- ?o=project__customer__name
- ?o=project__name
- ?o=project__project_groups__name
- ?o=agreed_sla
- ?o=slas__value  (order by actual_sla field)
