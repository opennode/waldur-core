Migration from IaaS
-------------------

Endpoints
+++++++++

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


Data migration
++++++++++++++

0. Create database backup.

1. Create shared service settings for new OpenStack and Zabbix.

2. Run migration command with "dry-run" option to test data migration:

   .. code-block:: bash

       nodeconductor iaas2openstack --dry-run

3. Run migration command without "dry-run" option:

   .. code-block:: bash

       nodeconductor iaas2openstack

4. From version 0.96.0 NodeConductor creates Zabbix Host and ITService for each created instance automatically.
   To prevent conflicts with template groups creation we need to make sure that there is no templates that
   creates Host or ITService.

   Execute next code in shell to delete all such templates or delete them manually:

   .. code-block:: python

       from nodeconductor_zabbix.models import Host, ITService
       from nodeconductor.template.models import Template

       for template in Template.objects.all():
           if template.object_content_type.model_class() in (Host, ITService):
               print template
               template.delete()

5. To enable Hosts autocreation - add next line to settings:

   .. code-block:: python

        settings.NODECONDUCTOR['IS_ITACLOUD'] = True.

6. Add KillBill settings to nodeconductor_plus.py

7. Check is there any instances without tags:

   .. code-block:: python

       from nodeconductor.structure.models import ResourceMixin

       for model in ResourceMixin.get_all_models():
           print model.__name__, '\n', [i.name for i in model.objects.all() if not i.tags.all()]

8. Make sure that template groups tags are right.
