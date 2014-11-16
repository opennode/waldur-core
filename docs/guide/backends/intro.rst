Sharable services
-----------------

NodeConductor is designed to support multiple API-based services for access sharing. Services can range from IaaS to
SaaS, the common denominator is ability to control services over APIs. Currently supported services are listed below.

OpenStack (private cloud, volume-based VMs)
+++++++++++++++++++++++++++++++++++++++++++

OpenStack is a popular open-source toolkit for building private clouds.

TODO: describe account model (admin -> service accounts)

VM creation
===========

When VM instance is created through NodeConductor, it is created as a volume-based image with two volumes:

- **root volume** containing OS root image
- **data volume** an empty volume for data

VM resize (flavor)
==================

In order to upgrade memory/cpu number a flavor should be changed. Pleas note, that disk size is not affected.
For security reasons - in general case not all OSs handle virtual hardware modifications correctly - only offline
upgrade is allowed.

VM resize (disk)
================

Increasing a disk size means extension of the **data volume** attached to the instance. The process includes
detaching of a data volume, extending it and re-attaching to a VM.


