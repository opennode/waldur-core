from django import forms
from django.contrib.contenttypes.models import ContentType

from nodeconductor.structure import models as structure_models
from nodeconductor.template.models import Template


class TemplateForm(forms.ModelForm):
    """ Form with list of options that could be specified for particular resource template.

        Form will use registered serializer to serialize options and store them in template.
    """
    service_settings = forms.ModelChoiceField(
        label="Service settings",
        queryset=structure_models.ServiceSettings.objects.all(),
        required=False)
    project = forms.ModelChoiceField(label="Project", queryset=structure_models.Project.objects.all(), required=False)
    use_previous_resource_project = forms.BooleanField(
        label='Use project of the previous resource', initial=False, required=False)

    class Meta:
        model = Template
        fields = ('order_number', 'project', 'service_settings', 'tags')

    def __init__(self, *args, **kwargs):
        instance = kwargs.get('instance')
        initial = kwargs.get('initial', {})
        if instance is not None:
            initial.update(self.deserialize(instance))
        kwargs['initial'] = initial
        super(TemplateForm, self).__init__(*args, **kwargs)
        self.fields['tags'].required = False

    @classmethod
    def get_serializer_class(cls):
        raise NotImplementedError()

    @classmethod
    def get_resource_model(cls):
        """ Get model of resource which provision parameters are described by form """
        raise NotImplementedError()

    @classmethod
    def set_request(cls, request):
        """ Hook that allows to add request to form on form creation """
        cls.request = request

    def serialize(self, data):
        """ Serialize form data for provision request """
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(context={'request': self.request})
        return {k: v for k, v in serializer.to_representation(data).items() if v}

    def deserialize(self, template):
        """ Deserialize default provision request options to form initials """
        serializer_class = self.get_serializer_class()
        serializer = serializer_class()
        data = {k: v for k, v in template.options.items() if v}
        return serializer.to_internal_value(data)

    @classmethod
    def get_resource_content_type(cls):
        """ Get a content type of resource connected to form in TemplateRegistry """
        resource = cls.get_resource_model()
        return ContentType.objects.get_for_model(resource)

    def save(self, **kwargs):
        """ Serialize form data with template serializer and save serialized data into template """
        self.instance.group = self.cleaned_data.pop('group')
        self.instance.order_number = self.cleaned_data.pop('order_number')
        self.instance.use_previous_resource_project = self.cleaned_data.pop('use_previous_resource_project')
        if self.cleaned_data.get('service'):
            self.instance.service_settings = self.cleaned_data['service'].settings
        if self.cleaned_data.get('service_settings'):
            self.instance.service_settings = self.cleaned_data['service_settings']
        self.instance.options = self.serialize(self.cleaned_data)
        self.instance.resource_content_type = self.get_resource_content_type()
        self.instance.save()
        self.instance.tags.clear()
        for tag in self.cleaned_data.pop('tags', []):
            self.instance.tags.add(tag)
        return self.instance
