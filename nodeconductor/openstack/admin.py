import pytz

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms import ModelForm
from django.utils.translation import ungettext

from nodeconductor.core.tasks import send_task
from nodeconductor.core.models import SynchronizationStates
from nodeconductor.structure import admin as structure_admin
from nodeconductor.openstack.models import OpenStackService, OpenStackServiceProjectLink, Instance, \
                                           Backup, BackupSchedule


class ServiceProjectLinkAdmin(structure_admin.ServiceProjectLinkAdmin):

    actions = structure_admin.ServiceProjectLinkAdmin.actions + \
              ['detect_external_networks', 'allocate_floating_ip']

    def detect_external_networks(self, request, queryset):
        queryset = queryset.exclude(state=SynchronizationStates.ERRED)

        tasks_scheduled = 0

        for spl in queryset.iterator():
            send_task('openstack', 'sync_external_network')(spl.to_string(), 'detect')
            tasks_scheduled += 1

        message = ungettext(
            'One service project link scheduled for detection',
            '%(tasks_scheduled)d service project links scheduled for detection',
            tasks_scheduled
        )
        message = message % {
            'tasks_scheduled': tasks_scheduled,
        }

        self.message_user(request, message)

    detect_external_networks.short_description = "Attempt to lookup and set external network id of the connected router"

    def allocate_floating_ip(self, request, queryset):
        queryset = queryset.exclude(state=SynchronizationStates.ERRED).exclude(external_network_id='')

        tasks_scheduled = 0

        for spl in queryset.iterator():
            send_task('openstack', 'allocate_floating_ip')(spl.to_string())
            tasks_scheduled += 1

        message = ungettext(
            'One service project link scheduled for floating IP allocation',
            '%(tasks_scheduled)d service project links scheduled for floating IP allocation',
            tasks_scheduled
        )
        message = message % {
            'tasks_scheduled': tasks_scheduled,
        }

        self.message_user(request, message)

    allocate_floating_ip.short_description = "Allocate floating IPs for selected service project links"


class BackupAdmin(admin.ModelAdmin):
    readonly_fields = ('created_at', 'kept_until',)
    list_filter = ('uuid', 'state')
    list_display = ('uuid', 'instance', 'state')


class BackupScheduleForm(ModelForm):
    def clean_timezone(self):
        tz = self.cleaned_data['timezone']
        if tz not in pytz.all_timezones:
            raise ValidationError('Invalid timezone', code='invalid')

        return self.cleaned_data['timezone']


class BackupScheduleAdmin(admin.ModelAdmin):
    form = BackupScheduleForm
    readonly_fields = ('next_trigger_at',)
    list_filter = ('is_active',)
    list_display = ('uuid', 'next_trigger_at', 'is_active', 'instance', 'timezone')


admin.site.register(Instance, structure_admin.ResourceAdmin)
admin.site.register(OpenStackService, structure_admin.ServiceAdmin)
admin.site.register(OpenStackServiceProjectLink, ServiceProjectLinkAdmin)
admin.site.register(Backup, BackupAdmin)
admin.site.register(BackupSchedule, BackupScheduleAdmin)
