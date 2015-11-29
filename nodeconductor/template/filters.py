import django_filters
import taggit

from nodeconductor.template import models


class TemplateGroupFilter(django_filters.FilterSet):
    tag = django_filters.ModelMultipleChoiceFilter(
        name='tags__name',
        to_field_name='name',
        lookup_type='in',
        queryset=taggit.models.Tag.objects.all(),
        conjoined=True,
    )

    class Meta(object):
        model = models.TemplateGroup
        fields = ['tag']
