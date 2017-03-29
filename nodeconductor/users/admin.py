from django import forms
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.utils.translation import ugettext_lazy as _

from nodeconductor.users import models


User = get_user_model()


class InvitationForm(forms.ModelForm):
    def clean(self):
        super(InvitationForm, self).clean()
        if any(self._errors):
            return

        customer_role = self.cleaned_data.get('customer_role')
        project_role = self.cleaned_data.get('project_role')
        if customer_role and project_role:
            raise forms.ValidationError(_('Cannot create invitation to project and customer simultaneously.'))
        elif not (customer_role or project_role):
            raise forms.ValidationError(_('Customer role or project role must be provided.'))
        elif User.objects.filter(email=self.cleaned_data['email']).exists():
            raise forms.ValidationError(_('User with provided email already exists.'))


class InvitationAdmin(admin.ModelAdmin):
    form = InvitationForm
    fields = ('email', 'project_role', 'customer_role', 'state', 'error_message', 'modified', 'created')
    readonly_fields = ('created', 'modified', 'error_message')
    list_display = ('email', 'uuid', 'project_role', 'customer_role', 'state')
    list_filter = ('state',)
    search_fields = ('email', 'uuid')

    def save_model(self, request, obj, form, change):
        if obj.project_role is not None:
            obj.customer = obj.project_role.project.customer
        else:
            obj.customer = obj.customer_role.customer
        return super(InvitationAdmin, self).save_model(request, obj, form, change)

admin.site.register(models.Invitation, InvitationAdmin)
