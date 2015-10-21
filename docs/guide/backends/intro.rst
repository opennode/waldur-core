Shareable services
------------------

NodeConductor is designed to support multiple API-based services for access sharing. Services can range from IaaS to
SaaS, the common denominator is the ability to control services over APIs. Currently supported services are listed below.

+------------------+----------------+--------+---------+---------------------------+----------+------------+
| Backend          | Provision      | Import | Destroy | Manage                    | Monitor  | Backup     |
+==================+================+========+=========+===========================+==========+============+
| Amazon *         | -              | yes    | -       | -                         | –        | –          |
+------------------+----------------+--------+---------+---------------------------+----------+------------+
| Azure *          | VirtualMachine | yes    | yes     | restart                   | –        | –          |
+------------------+----------------+--------+---------+---------------------------+----------+------------+
| DigitalOcean *   | VirtualMachine | yes    | yes     | start/stop/restart        | –        | –          |
+------------------+----------------+--------+---------+---------------------------+----------+------------+
| GitLab *         | Group, Project | yes    | yes     | –                         | –        | –          |
+------------------+----------------+--------+---------+---------------------------+----------+------------+
| Jira             | –              | –      | –       | –                         | –        | –          |
+------------------+----------------+--------+---------+---------------------------+----------+------------+
| OpenStack        | VirtualMachine | yes    | yes     | start/stop/restart/resize | zabbix   | snapshots  |
+------------------+----------------+--------+---------+---------------------------+----------+------------+
| Oracle           | DataBase       | –      | –       | start/stop/restart        | –        | –          |
+------------------+----------------+--------+---------+---------------------------+----------+------------+
| SugarCRM         | CRM            | –      | yes     | –                         | –        | –          |
+------------------+----------------+--------+---------+---------------------------+----------+------------+

\* available via NodeConductor extensions

OpenStack (private cloud, volume-based VMs)
+++++++++++++++++++++++++++++++++++++++++++

OpenStack_ is a popular open-source toolkit for building private clouds.

VM creation
===========

When a VM instance is created through NodeConductor, it is created as a bootable from volume. The following two
volumes are created:

- **root volume** containing OS root image
- **data volume** an empty volume for data

VM resize (flavor)
==================

To change memory or CPU number, a flavor should be changed. Please note, that the disk size is not affected.
Change can happen only for a stopped VM.

VM resize (disk)
================

Increasing a disk size means extension of the **data volume** attached to the instance. The process includes
detaching of a data volume, extending it and re-attaching to a VM. Disk can be increased only for a stopped VM.


.. _OpenStack: http://www.openstack.org/
