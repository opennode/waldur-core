Floating IPs
------------

To get a list of all available floating IPs, issue GET against **/api/floating-ips/**.
Floating IPs are read only. Each floating IP has fields: 'address', 'status'.

Status *DOWN* means that floating IP is not linked to a VM, status *ACTIVE* means that it is in use.

Floating IPs can be filtered by:

- ?cloud=<customer uuid>
- ?status=<floating_ip status>
- ?project=<project uuid>
