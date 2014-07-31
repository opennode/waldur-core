from django.contrib import admin
from django import forms

from nodeconductor.structure import models
from nodeconductor.cloud.models import Cloud

class CloudAdminForm(forms.ModelForm):
    clouds = forms.ModelMultipleChoiceField(Cloud.objects.all())

    def __init__(self, *args, **kwargs):
        super(CloudAdminForm, self).__init__(*args, **kwargs)
        if self.instance.pk:
            self.initial['clouds'] = self.instance.tags.values_list('pk', flat=True)

    def save(self, *args, **kwargs):
        instance = super(CloudAdminForm, self).save(*args, **kwargs)
        if instance.pk:
            instance.tags.clear()
            instance.tags.add(*self.cleaned_data['tags'])
        return instance

class ProjectAdmin(admin.ModelAdmin):
    form = CloudAdminForm

admin.site.register(models.Organization)
admin.site.register(models.Project, ProjectAdmin)
admin.site.register(models.Environment)
