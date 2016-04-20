from django.contrib import admin

from nodeconductor.template import models, TemplateRegistry


class BaseTemplateInline(admin.StackedInline):
    model = models.Template
    extra = 0
    max_num = 1

    def get_formset(self, request, obj=None, **kwargs):
        self.form.set_request(request)
        return super(BaseTemplateInline, self).get_formset(request, obj, **kwargs)

    def get_queryset(self, request):
        qs = super(BaseTemplateInline, self).get_queryset(request)
        return qs.filter(object_content_type=self.form.get_content_type())


class TemplateGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'uuid', 'is_active')

    def get_inlines(self):
        if not hasattr(self, '_inlines'):
            self._inlines = []
            for model in TemplateRegistry.get_models():
                template_form = TemplateRegistry.get_form(model)

                class TemplateInline(BaseTemplateInline):
                    form = template_form
                    verbose_name = "Template for %s %s provision" % (
                        model._meta.app_label, model._meta.verbose_name)
                    verbose_name_plural = "Templates for %s %s provision" % (
                        model._meta.app_label, model._meta.verbose_name)

                self._inlines.append(TemplateInline)
        return self._inlines

    def add_view(self, *args, **kwargs):
        self.inlines = self.get_inlines()
        return super(TemplateGroupAdmin, self).add_view(*args, **kwargs)

    def change_view(self, *args, **kwargs):
        self.inlines = self.get_inlines()
        return super(TemplateGroupAdmin, self).change_view(*args, **kwargs)

admin.site.register(models.TemplateGroup, TemplateGroupAdmin)
