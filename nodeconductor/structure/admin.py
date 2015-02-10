from django.contrib import admin

from nodeconductor.structure import models


class ProjectAdmin(admin.ModelAdmin):

    fields = ('name', 'description', 'customer')

    list_display = ['name', 'uuid', 'customer']
    search_fields = ['name', 'uuid']
    readonly_fields = ['customer']


class ProjectGroupAdmin(admin.ModelAdmin):

    fields = ('name', 'description', 'customer')

    list_display = ['name', 'uuid', 'customer']
    search_fields = ['name', 'uuid']
    readonly_fields = ['customer']


admin.site.register(models.Customer)
admin.site.register(models.Project, ProjectAdmin)
admin.site.register(models.ProjectGroup, ProjectGroupAdmin)
