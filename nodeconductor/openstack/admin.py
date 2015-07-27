from django.contrib import admin

from nodeconductor.structure import admin as structure_admin
from nodeconductor.openstack.models import OpenStackService, OpenStackServiceProjectLink, Instance


admin.site.register(Instance, structure_admin.ResourceAdmin)
admin.site.register(OpenStackService, structure_admin.ServiceAdmin)
admin.site.register(OpenStackServiceProjectLink, structure_admin.ServiceProjectLinkAdmin)
