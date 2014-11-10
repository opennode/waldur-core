from django.contrib import admin

from nodeconductor.cloud import models


class FlavorInline(admin.TabularInline):
    model = models.Flavor
    extra = 1


class CloudAdmin(admin.ModelAdmin):
    inlines = (
        FlavorInline,
    )
    list_display = ('name', 'customer')
    ordering = ('name', 'customer')


class SecurityGroupRuleInline(admin.TabularInline):
    model = models.SecurityGroupRule
    extra = 1


class SecurityGroupAdmin(admin.ModelAdmin):
    inlines = (
        SecurityGroupRuleInline,
    )
    list_display = ('cloud_project_membership', 'name')
    ordering = ('cloud_project_membership', 'name')


admin.site.register(models.Cloud, CloudAdmin)
admin.site.register(models.SecurityGroup, SecurityGroupAdmin)
