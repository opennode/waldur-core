
from django.contrib import admin

from nodeconductor.structure.admin import HiddenServiceAdmin

from nodeconductor.oracle.models import OracleService


admin.site.register(OracleService, HiddenServiceAdmin)
