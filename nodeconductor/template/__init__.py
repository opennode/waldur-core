"""
Template application allows provisioning of one or more resources with pre-defined parameters in a sequential order.


To enable an application to be part of a template, the following steps are required:

    1. Define <YourApplication>TemplateForm that will inherit from nodeconductor.template.forms.TemplateForm and
       describe template fields.

    2. Implement form methods:
     - get_model - this method should return model of resource or service that will be provisioned by template.
     - get_serializer_class - this method should return serializer that will be used for form fields serialization for
                              requests execution.
                              It is highly recommended to use nodeconductor.template.serializers.BaseTemplateSerializer.
                              Alternatively it is possible to override methods serialize() and desrialize().

        Example:

        .. code-block:: python

            class HostProvisionTemplateForm(TemplateForm):
                service = forms.ModelChoiceField(
                    label='Zabbix service', queryset=models.ZabbixService.objects.all(), required=False)
                name = forms.CharField(label='Name', required=False)
                visible_name = forms.CharField(label='Visible name', required=False)
                host_group_name = forms.CharField(label='Host group name', required=False)

                class Meta(TemplateForm.Meta):
                    fields = TemplateForm.Meta.fields + ('name', 'visible_name', 'host_group_name')

                class Serializer(BaseTemplateSerializer):
                    service = serializers.HyperlinkedRelatedField(
                        view_name='zabbix-detail',
                        queryset=models.ZabbixService.objects.all(),
                        lookup_field='uuid',
                        required=False,
                    )
                    name = serializers.CharField(required=False)
                    visible_name = serializers.CharField(required=False)
                    host_group_name = serializers.CharField(required=False)

                @classmethod
                def get_serializer_class(cls):
                    return cls.Serializer

                @classmethod
                def get_resource_model(cls):
                    return models.Host

    3. Register form in nodeconductor.template.TemplateRegistry:

        .. code-block:: python

            TemplateRegistry.register(HostProvisionTemplateForm)


Check API docs for description of template endpoints and workflow.

"""

default_app_config = 'nodeconductor.template.apps.TemplateConfig'


class TemplateRegistry(object):
    """ Registry of all template applications """

    _registry = {}

    @classmethod
    def register(cls, form):
        cls._registry[form.get_model()] = form

    @classmethod
    def get_models(cls):
        return cls._registry.keys()

    @classmethod
    def get_form(cls, model):
        return cls._registry[model]
