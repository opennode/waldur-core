from django.contrib import admin

from nodeconductor.iaas import models

admin.site.register(models.Instance)
