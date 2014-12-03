Shareable services
------------------

NodeConductor is designed to support multiple API-based services for access sharing. Services can range from IaaS to
SaaS, the common denominator is the ability to control services over APIs. Currently supported services are listed below.

OpenStack (private cloud, volume-based VMs)
+++++++++++++++++++++++++++++++++++++++++++

OpenStack_ is a popular open-source toolkit for building private clouds.

TODO: describe account model (admin -> service accounts)

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
