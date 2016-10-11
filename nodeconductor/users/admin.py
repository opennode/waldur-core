from django import forms
from django.contrib import admin

from nodeconductor.structure import models as structure_models
from nodeconductor.users import models


def _get_project_role_display(project_role):
    role_type = project_role.role_type
    role = ''
    for choice in structure_models.ProjectRole.TYPE_CHOICES:
        if choice[0] == role_type:
            role = choice[1]

    return '%s | %s' % (project_role.project.name, role)


class InvitationForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(InvitationForm, self).__init__(*args, **kwargs)
        # It should be clear from the name what project and role are going to be selected.
        self.fields['project_role'].label_from_instance = _get_project_role_display


class InvitationAdmin(admin.ModelAdmin):
    form = InvitationForm
    list_display = ('email', 'uuid', 'get_project', 'get_role', 'state')
    list_filter = ('state',)
    search_fields = ('email', 'uuid')

    def get_project(self, obj):
        return obj.project_role.project

    get_project.short_description = 'Project'
    get_project.admin_order_field = 'project_role__project'

    def get_role(self, obj):
        role_type = obj.project_role.role_type
        for choice in structure_models.ProjectRole.TYPE_CHOICES:
            if choice[0] == role_type:
                return choice[1]

    get_role.short_description = 'Role'
    get_role.admin_order_field = 'project_role__role_type'

admin.site.register(models.Invitation, InvitationAdmin)
