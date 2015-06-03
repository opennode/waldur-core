
from django.contrib import admin

from nodeconductor.structure.admin import HiddenServiceAdmin

from nodeconductor.oracle.models import OracleService, Database


class DatabaseAdmin(admin.ModelAdmin):
    list_display = ('name', 'backend_id', 'state')
    list_filter = ('state',)


admin.site.register(OracleService, HiddenServiceAdmin)
admin.site.register(Database, DatabaseAdmin)
