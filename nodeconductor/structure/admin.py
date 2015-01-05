from django.contrib import admin
from django import forms

from nodeconductor.structure import models
from nodeconductor.iaas.models import Cloud, CloudProjectMembership


class ProjectAdmin(admin.ModelAdmin):

    fields = ('name', 'description', 'customer')

    list_display = ['name', 'uuid']
    search_fields = ['name', 'uuid']
    readonly_fields = ['customer']


class ProjectGroupAdmin(admin.ModelAdmin):

    fields = ('name', 'description', 'customer')

    list_display = ['name', 'uuid']
    search_fields = ['name', 'uuid']
    readonly_fields = ['customer']


admin.site.register(models.Customer)
admin.site.register(models.Project, ProjectAdmin)
admin.site.register(models.ProjectGroup, ProjectGroupAdmin)
