from django.contrib import admin

from nodeconductor.structure import admin as structure_admin
from nodeconductor.oracle.models import OracleService, OracleServiceProjectLink, Database


admin.site.register(Database, structure_admin.ResourceAdmin)
admin.site.register(OracleService, structure_admin.ServiceAdmin)
admin.site.register(OracleServiceProjectLink, structure_admin.ServiceProjectLinkAdmin)
