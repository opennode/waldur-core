import six
from urlparse import urlparse

from django.contrib.contenttypes.models import ContentType
from django.core.urlresolvers import resolve
import django_filters
from rest_framework import filters

from nodeconductor.core import serializers as core_serializers, fields as core_fields


class DjangoMappingFilterBackend(filters.DjangoFilterBackend):
    """
    A filter backend that uses django-filter that fixes order_by.

    This backend supports additional attribute of a FilterSet named `order_by_mapping`.
    It maps ordering fields from user friendly ones to the ones that depend on
    the model relation innards.

    See https://github.com/alex/django-filter/issues/178#issuecomment-62129586

    Example usage:

    # models.py

    class Project(models.Model):
        name = models.CharField(max_length=10)


    class Instance(models.Model):
        name = models.CharField(max_length=10)
        instance = models.ForeignKey(Project)

    # filters.py

    class InstanceFilter(django_filters.FilterSet):
        class Meta(object):
            model = models.Instance

            # Filter fields go here
            order_by = [
                'name',
                '-name',
                'project__name',
                '-project__name',
            ]
            order_by_mapping = {
                # Fix order by parameters
                'project_name': 'project__name',
                # '-project_name' mapping is handled automatically
            }
    """

    def filter_queryset(self, request, queryset, view):
        filter_class = self.get_filter_class(view, queryset)

        if filter_class:
            # XXX: The proper way would be to redefine FilterSetOptions,
            # but it's too much of a boilerplate
            mapping = getattr(filter_class.Meta, 'order_by_mapping', None)
            order_by_field = getattr(filter_class, 'order_by_field')

            if mapping:
                transform = lambda o: self._transform_ordering(mapping, o)

                params = request.query_params.copy()
                ordering = map(transform, params.getlist(order_by_field))
                params.setlist(order_by_field, ordering)
            else:
                params = request.query_params

            return filter_class(params, queryset=queryset).qs

        return queryset

    # noinspection PyMethodMayBeStatic
    def _transform_ordering(self, mapping, ordering):
        if ordering.startswith('-'):
            ordering = ordering[1:]
            reverse = True
        else:
            reverse = False

        try:
            ordering = mapping[ordering]
        except KeyError:
            pass

        if reverse:
            return '-' + ordering

        return ordering


class MappedChoiceFilter(django_filters.ChoiceFilter):
    """
    A choice field that maps enum values from representation to model ones and back.

    Filter analog for MappedChoiceField
    """

    def __init__(self, choice_mappings, **kwargs):
        super(MappedChoiceFilter, self).__init__(**kwargs)

        # TODO: enable this assert then filtering by numbers will be disabled
        # assert set(k for k, _ in self.field.choices) == set(choice_mappings.keys()), 'Choices do not match mappings'
        assert len(set(choice_mappings.values())) == len(choice_mappings), 'Mappings are not unique'

        self.mapped_to_model = choice_mappings
        self.model_to_mapped = {v: k for k, v in six.iteritems(choice_mappings)}

    def filter(self, qs, value):
        if value in self.mapped_to_model:
            value = self.mapped_to_model[value]
        return super(MappedChoiceFilter, self).filter(qs, value)


class URLFilter(django_filters.CharFilter):
    """ Filter by hyperlinks. ViewSet name must be supplied in order to validate URL. """

    def __init__(self, viewset=None, **kwargs):
        super(URLFilter, self).__init__(**kwargs)
        self.viewset = viewset

    def filter(self, qs, value):
        uuid = ''
        path = urlparse(value).path
        if path.startswith('/'):
            url = resolve(path)
            if url.func.cls is self.viewset:
                pk_name = getattr(url.func.cls, 'lookup_field', 'pk')
                uuid = url.kwargs.get(pk_name)

        return super(URLFilter, self).filter(qs, uuid)


class GenericKeyFilter(django_filters.CharFilter):
    """
    Filter by generic key.

    Filter analog for GenericRelatedField.
    """

    def __init__(self, content_type_field='content_type', object_id_field='object_id', related_models=(), **kwargs):
        super(GenericKeyFilter, self).__init__(**kwargs)
        self.content_type_field = content_type_field
        self.object_id_field = object_id_field
        self.related_models = related_models

    def filter(self, qs, value):
        if value:
            field = core_serializers.GenericRelatedField(related_models=self.related_models)
            obj = field.to_internal_value(value)
            ct = ContentType.objects.get_for_model(obj)
            return qs.filter(**{self.object_id_field: obj.id, self.content_type_field: ct})
        return qs


class TimestampFilter(django_filters.NumberFilter):
    """
    Filter for dates in timestamp format
    """
    def filter(self, qs, value):
        if value:
            field = core_fields.TimestampField()
            datetime_value = field.to_internal_value(value)
            return super(TimestampFilter, self).filter(qs, datetime_value)
        return qs
