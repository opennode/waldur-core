
from django.contrib import admin
from django.utils.translation import ungettext

from nodeconductor.core.tasks import send_task
from nodeconductor.core.models import SynchronizationStates
from nodeconductor.structure.admin import HiddenServiceAdmin
from nodeconductor.openstack.models import OpenStackService, OpenStackServiceProjectLink


class OpenStackServiceProjectLinkAdmin(admin.ModelAdmin):
    readonly_fields = ('service', 'project')
    list_display = ('get_service_name', 'get_customer_name', 'get_project_name', 'state', 'tenant_id')
    ordering = ('service__customer__name', 'project__name', 'service__name')
    list_display_links = ('get_service_name',)
    search_fields = ('service__customer__name', 'project__name', 'service__name')

    actions = ['sync_with_backend']

    def get_queryset(self, request):
        queryset = super(OpenStackServiceProjectLinkAdmin, self).get_queryset(request)
        return queryset.select_related('service', 'project', 'project__customer')

    def sync_with_backend(self, request, queryset):
        queryset = queryset.filter(state=SynchronizationStates.IN_SYNC)
        send_task('structure', 'sync_service_project_links')([spl.to_string() for spl in queryset])

        tasks_scheduled = queryset.count()
        message = ungettext(
            'One service project link scheduled for update',
            '%(tasks_scheduled)d service project links scheduled for update',
            tasks_scheduled
        )
        message = message % {'tasks_scheduled': tasks_scheduled}

        self.message_user(request, message)

    sync_with_backend.short_description = "Sync selected service project links with backend"

    def get_service_name(self, obj):
        return obj.service.name

    get_service_name.short_description = 'Service'

    def get_project_name(self, obj):
        return obj.project.name

    get_project_name.short_description = 'Project'

    def get_customer_name(self, obj):
        return obj.service.customer.name

    get_customer_name.short_description = 'Customer'


admin.site.register(OpenStackService, HiddenServiceAdmin)
admin.site.register(OpenStackServiceProjectLink, OpenStackServiceProjectLinkAdmin)
