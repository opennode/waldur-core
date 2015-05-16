
from django import forms

from nodeconductor.iaas.models import IaasTemplateService


class IaasTemplateServiceAdminForm(forms.ModelForm):

    class Meta:
        model = IaasTemplateService
        exclude = []
