OpenStack configuration
=======================

In order to link OpenStack with NodeConductor you need to set credentials of an OpenStack
administrative user in NodeConductor settings.

**NodeConductor configuration examples**

1. Django settings if installed from sources.

    .. code-block:: python

        NODECONDUCTOR = {
            'OPENSTACK_CREDENTIALS': (
                {
                    'auth_url': 'http://keystone.example.com:5000/v2.0',
                    'username': 'node',
                    'password': 'conductor',
                    'tenant_name': 'admin',
                },
            ),
        }

2. Configuration file if installed from package.

    .. code-block:: ini

        [openstack]
        auth_url = http://keystone.example.com:5000/v2.0
        username = nodeconductor
        password = nodeconductor
        tenant_name = admin

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

It's possible to emulate interaction with OpenStack by creating dummy clouds as follows:

.. code-block:: python

    cloud = Cloud.objects.create(
        customer=customer,
        name='Dummy Cloud',
        dummy=True,
        auth_url='http://keystone.example.com:5000/v2.0',
    )

    # Valid credentials for dummy OpenStack are:
    #    auth_url = 'http://keystone.example.com:5000/v2.0'
    #    username = 'test_user'
    #    password = 'test_password'
    #    tenant_name = 'test_tenant'
    #    tenant_id = '593af1f7b67b4d63b691fcabd2dad126'
