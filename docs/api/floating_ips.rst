Floating IPs
------------

Tenant floating IPs (read only). Each floating IP has fields: 'address', 'status'.

URL: /api/floating-ips/

Floating IPs can be filtered by:
 - ?cloud=<customer uuid>
 - ?status=< floating_ip status>
 - ?project=<project uuid>
