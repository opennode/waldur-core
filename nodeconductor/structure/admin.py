from django.contrib import admin

from nodeconductor.structure import models

admin.site.register(models.Organisation)
admin.site.register(models.Project)
admin.site.register(models.Environment)
