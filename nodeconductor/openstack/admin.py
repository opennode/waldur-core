from django.contrib import admin

from nodeconductor.structure import admin as structure_admin
from nodeconductor.openstack.models import Service, ServiceProjectLink


admin.site.register(Service, structure_admin.ServiceAdmin)
admin.site.register(ServiceProjectLink, structure_admin.ServiceProjectLinkAdmin)
