from django.contrib import admin

from nodeconductor.structure import models

admin.site.register(models.Organization)
admin.site.register(models.Project)
admin.site.register(models.Environment)
