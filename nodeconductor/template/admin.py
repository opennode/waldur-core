
from django.contrib import admin
from polymorphic.admin import (
    PolymorphicParentModelAdmin, PolymorphicChildModelAdmin,
    PolymorphicChildModelFilter,
)

from nodeconductor.template import get_template_services
from nodeconductor.template.models import Template, TemplateService


all_services = []
admin_inlines = []
for service in get_template_services():
    class StandardAdminClass(PolymorphicChildModelAdmin):
        base_model = TemplateService

    class InlineAdminClass(admin.StackedInline):
        readonly_fields = ['templateservice_ptr']
        model = service
        extra = 1

    if service._admin_form:
        StandardAdminClass.form = service._admin_form
        InlineAdminClass.form = service._admin_form

    admin_inlines.append(InlineAdminClass)
    all_services.append((service, StandardAdminClass))


class TemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'uuid', 'is_active')

    def add_view(self, *args, **kwargs):
        self.inlines = tuple()
        return super(TemplateAdmin, self).add_view(*args, **kwargs)

    def change_view(self, *args, **kwargs):
        self.inlines = admin_inlines
        return super(TemplateAdmin, self).change_view(*args, **kwargs)


class TemplateServiceAdmin(PolymorphicParentModelAdmin):
    list_display = ('name', 'base_template')
    list_filter = (PolymorphicChildModelFilter,)
    base_model = TemplateService
    child_models = all_services


# admin.site.register(Template, TemplateAdmin)
# admin.site.register(TemplateService, TemplateServiceAdmin)
