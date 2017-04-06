from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline
from django.contrib.contenttypes import models as ct_models
from django.forms import ModelForm

from nodeconductor.core.admin import ReversionAdmin, ReadonlyTextWidget
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


class QuotaFieldTypeLimit(object):
    readonly_fields = ('quota_field_type',)

    def quota_field_type(self, obj):
        field = obj.get_field()
        if field:
            return field.__class__.__name__
        return ''


class QuotaForm(ModelForm):

    class Meta:
        model = models.Quota
        fields = ('name', 'limit', 'usage')
        readonly_fields = ('name', 'usage')

    def __init__(self, *args, **kwargs):
        super(QuotaForm, self).__init__(*args, **kwargs)

        if self.instance:
            for field in self.Meta.readonly_fields:
                self.fields[field].widget = ReadonlyTextWidget()

            if self._is_backend_quota_field(self.instance):
                self.fields['limit'].widget = ReadonlyTextWidget()

    def _is_backend_quota_field(self, quota):
        if quota.scope:
            field = getattr(quota.scope.Quotas, quota.name)
            return field.is_backend
        else:
            return False


class QuotaAdmin(QuotaFieldTypeLimit, ReversionAdmin):
    list_display = ['scope', 'name', 'limit', 'usage']
    list_filter = ['name', QuotaScopeClassListFilter]


class QuotaInline(QuotaFieldTypeLimit, GenericTabularInline):
    model = models.Quota
    form = QuotaForm
    extra = 0
    can_delete = False

admin.site.register(models.Quota, QuotaAdmin)
