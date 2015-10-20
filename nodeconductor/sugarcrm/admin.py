from django.contrib import admin

from nodeconductor.structure import admin as structure_admin
from nodeconductor.sugarcrm.models import SugarCRMServiceProjectLink, SugarCRMService, CRM


admin.site.register(CRM, structure_admin.ResourceAdmin)
admin.site.register(SugarCRMService, structure_admin.ServiceAdmin)
admin.site.register(SugarCRMServiceProjectLink, structure_admin.ServiceProjectLinkAdmin)
