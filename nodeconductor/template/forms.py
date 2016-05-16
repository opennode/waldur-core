from django import forms
from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers

from nodeconductor.structure import models as structure_models
from nodeconductor.template.models import Template


class TemplateForm(forms.ModelForm):
    use_previous_project = forms.BooleanField(
        label='Use project of the previous object', initial=False, required=False)
    project = forms.ModelChoiceField(label="Project", queryset=structure_models.Project.objects.all(), required=False)

    class Meta:
        model = Template
        fields = ('order_number', 'use_previous_project', 'project', 'tags')

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
    def get_model(cls):
        """ Get model of object which provision parameters are described by form """
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
        try:
            return serializer.to_internal_value(data)
        except serializers.ValidationError as e:
            # If some object disappears from DB serializer will throw error,
            # lets try remove such fields from data.
            for error_field in e.detail:
                if error_field in data:
                    del data[error_field]
            return serializer.to_internal_value(data)

    @classmethod
    def get_content_type(cls):
        """ Get a content type of object connected to form in TemplateRegistry """
        obj = cls.get_model()
        return ContentType.objects.get_for_model(obj)

    def save(self, **kwargs):
        """ Serialize form data with template serializer and save serialized data into template """
        self.instance.use_previous_project = self.cleaned_data.pop('use_previous_project')
        self.instance.group = self.cleaned_data.pop('group')
        self.instance.order_number = self.cleaned_data.pop('order_number')
        self.instance.options = self.serialize(self.cleaned_data)
        self.instance.object_content_type = self.get_content_type()
        self.instance.save()
        self.instance.tags.clear()
        for tag in self.cleaned_data.pop('tags', []):
            self.instance.tags.add(tag)
        return self.instance


class ServiceTemplateForm(TemplateForm):
    customer = forms.ModelChoiceField(
        queryset=structure_models.Customer.objects.all(),
        required=False)
    scope = forms.CharField(required=False)

    class Meta(TemplateForm.Meta):
        fields = TemplateForm.Meta.fields + ('customer', 'scope')


class ResourceTemplateForm(TemplateForm):
    """ Form with list of options that could be specified for particular object template.

        Form will use registered serializer to serialize options and store them in template.
    """
    service_settings = forms.ModelChoiceField(
        label="Service settings",
        queryset=structure_models.ServiceSettings.objects.all(),
        required=False)

    class Meta(TemplateForm.Meta):
        fields = TemplateForm.Meta.fields + ('service_settings',)

    def save(self, **kwargs):
        """ Serialize form data with template serializer and save serialized data into template """
        if self.cleaned_data.get('service'):
            self.instance.service_settings = self.cleaned_data['service'].settings
        if self.cleaned_data.get('service_settings'):
            self.instance.service_settings = self.cleaned_data['service_settings']
        return super(ResourceTemplateForm, self).save(**kwargs)
