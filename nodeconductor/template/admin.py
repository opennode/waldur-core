from django.contrib import admin
from polymorphic.admin import (
    PolymorphicParentModelAdmin, PolymorphicChildModelAdmin,
    PolymorphicChildModelFilter,
)

from nodeconductor.template import models


class TemplateServiceChildAdmin(PolymorphicChildModelAdmin):
    base_model = models.TemplateService


class TemplateServiceIaaSAdmin(TemplateServiceChildAdmin):
    pass


class TemplateServiceParentAdmin(PolymorphicParentModelAdmin):
    list_display = ('name', 'template')
    list_filter = (PolymorphicChildModelFilter,)
    base_model = models.TemplateService
    child_models = (
        (models.TemplateServiceIaaS, TemplateServiceIaaSAdmin),
    )


class TemplateServiceIaaSInline(admin.StackedInline):
    model = models.TemplateServiceIaaS
    readonly_fields = ('templateservice_ptr',)
    extra = 1


class TemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'uuid', 'is_active')
    inlines = (TemplateServiceIaaSInline,)


admin.site.register(models.Template, TemplateAdmin)
# admin.site.register(models.TemplateService, TemplateServiceParentAdmin)
