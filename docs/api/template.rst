List template groups
--------------------

To get a list of all template groups, issue GET request against **/api/templates-groups/**.

Supported filters are:

 - tag=<template group tag>, can be list.
 - project=<project_url> filter all template groups that could be provisioned with given project.


Example of response:


.. code-block:: javascript

    [
        {
            "url": "http://example.com/api/templates-groups/5a587c00ac1647ae9f9325423368a243/",
            "uuid": "5a587c00ac1647ae9f9325423368a243",
            "name": "templates group test",
            "icon_url": "",
            "description": "Some description",
            "templates": [
                // this template will be executed first because its order number is one.
                {
                    "uuid": "84242c11255b402dbbb7186265b8984b",
                    "options": {
                        "service": "http://example.com/api/openstack/582b6334b2574385b166f14a49742069/",
                        "image": "http://example.com/api/openstack-images/097a991b916a4f5796e3976c5684229f/",
                        "data_volume_size": 10240,
                        "project": "http://example.com/api/projects/dcd0c0751a5546939d642442eff8d008/",
                        "flavor": "http://example.com/api/openstack-flavors/6182198f954244cba3bea3c2c86e07e4/",
                        "system_volume_size": 10240
                    },
                    "resource_type": "OpenStack.Instance",
                    "resource_provision_url": "http://example.com/api/openstack-instances/",
                    "order_number": 1
                },
                {
                    "uuid": "e785631d67f84f54995385c02fcb40bd",
                    "options": {
                        "project": "http://example.com/api/projects/873d6858eabb4ec6b232b32da81d752a/",
                        "visible_name": "{{ response.name }}",
                        "name": "pavel-test-{{ response.uuid }}",
                        "service": "http://example.com/api/zabbix/0923177a994742dd97257d004d3afae3/"
                    },
                    "resource_type": "Zabbix.Host",
                    "resource_provision_url": "http://example.com/api/zabbix-hosts/",
                    "order_number": 2
                }
            ],
            "is_active": true
        }
    ]

Template field "order_number" shows templates execution order: template with lowest order number will be executed first.


Start template group provisioning
---------------------------------

To start a template group provisioning, issue POST request against **/api/templates-groups/<uuid>/provision/**
with a list of templates' additional options. Additional options should contain options for what should be added to
template options and passed to resource provisioning endpoint.

Additional options example:

.. code-block:: javascript

    [
        // options for first template
        {
            "name": "test-openstack-instance",
            "system_volume_size": 20
        },
        // options for second template
        {
            "host_group": "zabbix-host-group"
        }
    ]

If provision starts successfully, template group result object will be returned.


Get a list of template groups results
-------------------------------------

To get a list of template group results - issue POST request against **/api/templates-results/**.

Template group result has the following fields:

 - url
 - uuid
 - is_finished - false if corresponding template group is provisioning resources, true otherwise
 - is_erred - true if corresponding template group provisioning has failed
 - provisioned_resources - list of resources URLs that were provisioned by the template group
 - state_message - human-readable description of the state of the provisioning group
 - error_message - human-readable error message (empty if provisioning was successful)
 - error_details - technical details of the error

Response examples:

.. code-block:: javascript

    [
        // succeed
        {
            "url": "http://example.com/api/templates-results/78d2473769124248a19e5070c634e692/",
            "uuid": "78d2473769124248a19e5070c634e692",
            "is_finished": true,
            "is_erred": false,
            "provisioned_resources": {
                "Zabbix.Host": "http://example.com/api/zabbix-hosts/6fb9273115514b6ebf0d0140d41579bb/",
                "OpenStack.Instance": "http://example.com/api/openstack-instances/ee55107e32874814828524c99b866b13/"
            },
            "state_message": "Template group has been executed successfully.",
            "error_message": "",
            "error_details": ""
        },
        // failed
        {
            "url": "http://example.com/api/templates-results/ac04a5daf1f542b4b616da1a394956dd/",
            "uuid": "ac04a5daf1f542b4b616da1a394956dd",
            "is_finished": true,
            "is_erred": true,
            "provisioned_resources": {},
            "state_message": "Template group execution has been failed.",
            "error_message": "Failed to schedule nodeconductor_zabbix host provision.",
            "error_details": "POST request to URL http://example.com/api/zabbix-hosts/ failed...]}"
        }
    ]
