Declaring resource actions
--------------------------

Any methods on the resource viewset decorated with @detail_route(methods=['post'])
will be recognized as resource actions. For example:

.. code-block:: python

    class InstanceViewSet(structure_views.BaseResourceViewSet):

        @detail_route(methods=['post'])
        @safe_operation(valid_state=models.Resource.States.OFFLINE)
        def start(self, request, resource, uuid=None):
            pass

        @detail_route(methods=['post'])
        @safe_operation(valid_state=models.Resource.States.ONLINE)
        def stop(self, request, resource, uuid=None):
            pass


Rendering simple actions
++++++++++++++++++++++++

Given the previous example, the following metadata is rendered for actions
as response to OPTIONS request against resource endpoint
http://example.com/api/openstack-instances/a9edaa7357c84bd9855f1c0bf3305b49/

.. code-block:: javascript

    {
        "actions": {
            "destroy": {
                "title": "Destroy",
                "url": "http://example.com/api/openstack-instances/a9edaa7357c84bd9855f1c0bf3305b49/",
                "enabled": false,
                "reason": "Performing destroy operation is not allowed for resource in its current state",
                "destructive": true,
                "method": "DELETE"
            },
            "stop": {
                "title": "Stop",
                "url": "http://example.com/api/openstack-instances/a9edaa7357c84bd9855f1c0bf3305b49/stop/",
                "enabled": true,
                "reason": null,
                "destructive": false,
                "type": "button",
                "method": "POST"
            }
        }
    }

Simple actions, such as `stop` action, do not require any additional data.
So in order to apply `stop` action, you should issue `POST` request against endpoint specified in `url` field.

Some actions, such as start as stop, may be undone, but destroy action can't be.
In order to indicate it, set `destructive` attribute on the viewset method.
Usually such action is rendered on the frontend with `warning` indicator.

If you do not want to use the default title generated for your action,
set `title` attribute on the viewset method.

If action is not enabled for resource it is rendered on the frontend with `disabled` class and `reason` is shown as tooltip.

Complex actions and serializers
+++++++++++++++++++++++++++++++

If your action uses serializer to parse complex data, `get_serializer_class`
method on the resource viewset should return action-specific serializer. For example:

.. code-block:: python

    class InstanceViewSet(structure_views.BaseResourceViewSet):

        serializers = {
            'assign_floating_ip': serializers.AssignFloatingIpSerializer,
            'resize': serializers.InstanceResizeSerializer,
        }

        def get_serializer_class(self):
            serializer = self.serializers.get(self.action)
            return serializer or super(InstanceViewSet, self).get_serializer_class()

If your action uses additional input data, it has `form` type and list of fields rendered as metadata.
The following attributes are exposed for action's fields: label, help_text, min_length, max_length, min_value, max_value, many.

Filtering valid choices for action's fields
+++++++++++++++++++++++++++++++++++++++++++

In order to display only valid field choices to user in action's dialog,
ensure that serializer's fields define `query_params`, `value_field` and `display_name_field` attributes.
For example:

.. code-block:: python

    class AssignFloatingIpSerializer(serializers.Serializer):
        def get_fields(self):
            fields = super(AssignFloatingIpSerializer, self).get_fields()
            if self.instance:
                query_params = {
                    'status': 'DOWN',
                    'project': self.instance.service_project_link.project.uuid,
                    'service': self.instance.service_project_link.service.uuid
                }

                field = fields['floating_ip']
                field.query_params = query_params
                field.value_field = 'url'
                field.display_name_field = 'address'
            return fields

Given previous serializer the following metadata is rendered:

.. code-block:: javascript

    {
        "actions": {
            "assign_floating_ip": {
                "title": "Assign floating IP",
                "url": "http://example.com/api/openstack-instances/a9edaa7357c84bd9855f1c0bf3305b49/assign_floating_ip/",
                "fields": {
                    "floating_ip": {
                        "type": "select",
                        "required": true,
                        "label": "Floating IP",
                        "url": "http://example.com/api/openstack-floating-ips/?status=DOWN&project=01cfe887ba784a2faf054b2fcf464b6a&service=1547f5de7baa4dee80af5021629b76d9",
                        "value_field": "url",
                        "display_name_field": "address"
                    }
                },
                "enabled": true,
                "reason": null,
                "destructive": false,
                "type": "form",
                "method": "POST"
            }
        }
    }


Frontend uses list of fields supported by action in order to render dialog.
For fields with `select` type, `url` attribute specifies endpoint for fetching valid choices.
Choices are not rendered as is for performance reasons, think of huge list of choices.
Each object rendered by this endpoint should have attributes corresponding to value of `value_field` and `display_name_field`. They are used to render select choices.

Given query http://example.com/api/openstack-floating-ips/?status=DOWN&project=01cfe887ba784a2faf054b2fcf464b6a&service=1547f5de7baa4dee80af5021629b76d9 and the following list of floating IPs, only the last choice would be rendered as valid choice.

.. code-block:: javascript

    [
        {
            "url": "http://example.com/api/openstack-floating-ips/77d2551e38f941389e21a56b08f7f0f6/",
            "uuid": "77d2551e38f941389e21a56b08f7f0f6",
            "status": "ACTIVE",
            "address": "192.168.42.111",
            "service_project_link": {
                "project": "http://example.com/api/projects/4ed0ba732de745f68a01a24d1e82da05/",
                "service": "http://example.com/api/openstack/b0ee29d580d4479a8121f68878803442/"
            }
        },
        {
            "url": "http://example.com/api/openstack-floating-ips/65060b263e5a4ef1a5b4d6f51b113d0c/",
            "uuid": "65060b263e5a4ef1a5b4d6f51b113d0c",
            "status": "DOWN",
            "address": "192.168.42.203",
            "service_project_link": {
                "project": "http://example.com/api/projects/01cfe887ba784a2faf054b2fcf464b6a/",
                "service": "http://example.com/api/openstack/1547f5de7baa4dee80af5021629b76d9/"
            }
        }
    ]

