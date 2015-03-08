
from django import forms

from nodeconductor.iaas.models import IaasTemplateService


class IaasTemplateServiceAdminForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(IaasTemplateServiceAdminForm, self).__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['flavor'].queryset = self.instance.service.flavors.all()
            self.fields['image'].queryset = self.instance.service.images.all()

    class Meta:
        model = IaasTemplateService
        exclude = []
