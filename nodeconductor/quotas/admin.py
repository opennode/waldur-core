from django.contrib import admin
from django.contrib.contenttypes import models as ct_models, generic

from nodeconductor.quotas import models, utils


class QuotaScopeClassListFilter(admin.SimpleListFilter):
    # Human-readable title
    title = 'Scope class'

    # Parameter for the filter that will be used in the URL query
    parameter_name = 'scope_class'

    def lookups(self, request, model_admin):
        models = utils.get_models_with_quotas()
        return [(ct_models.ContentType.objects.get_for_model(m).id, m.__name__) for m in models]

    def queryset(self, request, queryset):
        content_type_id = self.value()
        if content_type_id:
            return queryset.filter(content_type_id=content_type_id)
        return queryset


class QuotaAdmin(admin.ModelAdmin):
    list_display = ['scope', 'name', 'limit', 'usage']
    list_filter = ['name', QuotaScopeClassListFilter]


class QuotaInline(generic.GenericTabularInline):
    model = models.Quota
    fields = ('name', 'limit', 'usage')
    readonly_fields = ('name',)
    extra = 0
    can_delete = False


admin.site.register(models.Quota, QuotaAdmin)
