from django.contrib import admin

from nodeconductor.ldapsync import models

admin.site.register(models.LdapToGroup)
