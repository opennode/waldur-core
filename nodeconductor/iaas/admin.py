from django.contrib import admin
from django.utils.translation import ungettext

from nodeconductor.cloud import models as cloud_models
from nodeconductor.core.models import SynchronizationStates
from nodeconductor.iaas import models
from nodeconductor.iaas import tasks


# Inspired by Django Snippet https://djangosnippets.org/snippets/2629/
class ReadonlyInlineMixin(object):
    can_delete = False
    extra = 0

    def has_add_permission(self, request):
        return False


class FlavorInline(admin.TabularInline):
    model = cloud_models.Flavor
    extra = 1


# noinspection PyMethodMayBeStatic
class CloudAdmin(admin.ModelAdmin):
    inlines = (
        FlavorInline,
    )
    list_display = ('name', 'customer')
    ordering = ('name', 'customer')

    actions = ['pull_clouds']

    def pull_clouds(self, request, queryset):
        queryset = queryset.filter(state=SynchronizationStates.IN_SYNC)

        tasks_scheduled = 0

        for cloud_account in queryset.iterator():
            cloud_account.schedule_syncing()
            cloud_account.save()

            tasks.pull_cloud_account.delay(cloud_account.uuid.hex)
            tasks_scheduled += 1

        message = ungettext(
            'One cloud account scheduled for update',
            '%(tasks_scheduled)d cloud accounts scheduled for update',
            tasks_scheduled
        )
        message = message % {
            'tasks_scheduled': tasks_scheduled,
        }

        self.message_user(request, message)

    pull_clouds.short_description = "Update from backend"


class InstanceAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ['template']
        return []
    ordering = ('hostname',)
    list_display = ['hostname', 'uuid', 'state', 'project', 'template', 'flavor']
    search_fields = ['hostname', 'uuid']
    list_filter = ['state', 'project', 'template']


class PurchaseAdmin(admin.ModelAdmin):
    readonly_fields = ('date', 'user', 'project')


class ImageInline(ReadonlyInlineMixin, admin.TabularInline):
    model = models.Image
    fields = ('get_cloud_name', 'get_customer_name', 'backend_id')
    readonly_fields = ('get_cloud_name', 'get_customer_name', 'backend_id')
    ordering = ('cloud__name', 'cloud__customer__name')
    verbose_name_plural = 'Connected cloud images'

    def get_cloud_name(self, obj):
        return obj.cloud.name
    get_cloud_name.short_description = 'Cloud'

    def get_customer_name(self, obj):
        return obj.cloud.customer.name
    get_customer_name.short_description = 'Customer'


class TemplateMappingInline(admin.TabularInline):
    model = models.TemplateMapping
    fields = ('description', 'backend_image_id')
    ordering = ('description', )
    extra = 3


class TemplateAdmin(admin.ModelAdmin):
    inlines = (
        TemplateMappingInline,
        ImageInline,
    )
    ordering = ('name', )
    list_display = ['name', 'uuid', 'sla_level']


class SecurityGroupRuleInline(admin.TabularInline):
    model = cloud_models.SecurityGroupRule
    extra = 1


class SecurityGroupAdmin(admin.ModelAdmin):
    inlines = (
        SecurityGroupRuleInline,
    )
    list_display = ('cloud_project_membership', 'name')
    ordering = ('cloud_project_membership', 'name')


admin.site.register(cloud_models.Cloud, CloudAdmin)
admin.site.register(models.Instance, InstanceAdmin)
admin.site.register(models.InstanceSlaHistory)
admin.site.register(models.Purchase, PurchaseAdmin)
admin.site.register(cloud_models.SecurityGroup, SecurityGroupAdmin)
admin.site.register(models.Template, TemplateAdmin)
