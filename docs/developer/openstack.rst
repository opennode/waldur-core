OpenStack configuration
=======================

In order to link OpenStack with NodeConductor you need to set credentials of an OpenStack
administrative user in NodeConductor settings. This could be done in corresponding Django admin section:
**/admin/iaas/openstacksettings/**

Create OpenStack Instance
-------------------------

Follow NodeConductor's structure and create an Instance representing your OpenStack configuration.
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
    )

    # Create descriptive template and map it with a glance image
    glance_image_id = 'd15dc2c4-25d6-4150-93fe-a412499298d8'
    template = Template.objects.create(
        name='CentOS 6',
        os='CentOS 6.5',
        sla_level=99.99,
        is_active=True,
    )
    template.mappings.create(backend_image_id=glance_image_id)

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

