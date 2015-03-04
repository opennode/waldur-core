from django.contrib import admin
from polymorphic.admin import (
    PolymorphicParentModelAdmin, PolymorphicChildModelAdmin,
    PolymorphicChildModelFilter,
)

from nodeconductor.template import models
from nodeconductor.template.utils import get_services


class TemplateServiceAdmin(PolymorphicChildModelAdmin):
    base_model = models.TemplateService


class TemplateServiceParentAdmin(PolymorphicParentModelAdmin):
    list_display = ('name', 'template')
    list_filter = (PolymorphicChildModelFilter,)
    base_model = models.TemplateService

    def get_child_models(self):
        child_models = [(service, TemplateServiceAdmin) for service in get_services()]
        if not child_models:
            raise RuntimeError("There's no any template service defined")

        return child_models


class TemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'uuid', 'is_active')


admin.site.register(models.Template, TemplateAdmin)
admin.site.register(models.TemplateService, TemplateServiceParentAdmin)
