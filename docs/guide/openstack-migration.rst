Migration from IaaS
===================

Correspondence between IaaS endpoints and OpenStack endpoints:

- /api/clouds/                    => `/api/openstack/`_
- /api/instances/                 => `/api/openstack-instances/`_
- /api/project-cloud-memberships/ => `/api/openstack-service-project-link/`_
- /api/template-licenses/         => `/api/openstack-licenses/`_
- /api/floating-ips/              => /api/openstack-floating-ips/
- /api/security-groups/           => /api/openstack-security-groups/
- /api/backups/                   => `/api/openstack-backups/`_
- /api/backup-schedules/          => `/api/openstack-backup-schedules/`_
- /api/flavors/                   => /api/openstack-flavors/
- /api/iaas-resources/            => /api/resources/ (with SLA filtering) + /api/resource-sla-state-transition/

.. _/api/openstack/: service.html
.. _/api/openstack-instances/: resource.html
.. _/api/openstack-service-project-link/: service.html#link-openstack-service-to-a-project
.. _/api/openstack-licenses/: licenses.html
.. _/api/openstack-backups/: backup.html#backup
.. _/api/openstack-backup-schedules/: backup.html#backup-schedules
