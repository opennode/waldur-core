from django.contrib import admin

from nodeconductor.structure import admin as structure_admin
from nodeconductor.oracle.models import Service, ServiceProjectLink, Database


admin.site.register(Database, structure_admin.ResourceAdmin)
admin.site.register(Service, structure_admin.ServiceAdmin)
admin.site.register(ServiceProjectLink, structure_admin.ServiceProjectLinkAdmin)
