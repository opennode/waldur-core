Shareable services
------------------

NodeConductor is designed to support multiple API-based services for access sharing. Services can range from IaaS to
SaaS, the common denominator is the ability to control services over APIs. Currently supported services are listed below.

OpenStack (private cloud, volume-based VMs)
+++++++++++++++++++++++++++++++++++++++++++

OpenStack_ is a popular open-source toolkit for building private clouds.

In order to link OpenStack with NodeConductor you merely have to supply credentials within Django settings.
Please check `configuration section <install-from-src.html#configuration>`__ for examples.

Follow `NodeConductor's structure <structure.html#customers>`__ and create an Instance representing your OpenStack configuration.
An extensive example provided below.

.. code-block:: python

    from nodeconductor.structure.models import Customer
    from nodeconductor.iaas.models import Cloud, CloudProjectMembership, Template, Instance


    # Create a customer representing your company or department
    customer = Customer.objects.create(
        name='Joe',
        native_name='Joe Doe',
        abbreviation='JD',
    )

    # Create general IaaS account representation
    # Make sure it's listed in django.conf.settings.NODECONDUCTOR.OPENSTACK_CREDENTIALS
    auth_url = 'http://keystone.example.com:5000/v2.0'
    cloud = Cloud.objects.create(
        customer=customer,
        name='Openstack Cloud',
        auth_url=auth_url,
    )

    # Create a project, NodeConductor's entity used to aggregate and isolate resources
    # User access management to projects and clouds is ommited in this guide
    project = customer.projects.create(
        name='My Project',
    )

    # Bind a cloud with a project
    cloud_project_membership = CloudProjectMembership.objects.create(
        project=project,
        cloud=cloud,
        tenant_id='593af1f7b67b4d63b691fcabd2dad126',
    )

    # Create descriptive template and map it with a glance image
    image_id = 'd15dc2c4-25d6-4150-93fe-a412499298d8'
    template = Template.objects.create(
        name='CentOS 6',
        os='CentOS 6.5',
        sla_level=99.99,
        is_active=True,
    )
    template.mappings.create(backend_image_id=image_id)

    # Pull images and flavors from a cloud backend
    backend = cloud.get_backend()
    backend.pull_cloud_account(cloud)

    # Create an instance of IaaS service
    flavor = cloud.flavors.first()
    instance = Instance.objects.create(
        hostname='example.com',
        template=template,
        agreed_sla=template.sla_level,
        system_volume_size=flavor.disk,
        ram=flavor.ram,
        cores=flavor.cores,
        cloud_project_membership=cloud_project_membership
    )

    # Instance is ready to be provisioned now
    backend.provision_instance(instance, flavor.backend_id)

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
