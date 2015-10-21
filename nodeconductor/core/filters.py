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
            # pass request as parameter to filter class if it expects such argument
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


class GenericKeyFilterBackend(filters.DjangoFilterBackend):
    """
    Backend for filtering by backend field.

    Methods 'get_related_models' and 'get_field_name' has to be implemented.
    Example:

        class AlertScopeFilterBackend(core_filters.GenericKeyFilterBackend):

            def get_related_models(self):
                return utils.get_loggable_models()

            def get_field_name(self):
                return 'scope'
    """
    content_type_field = 'content_type'
    object_id_field = 'object_id'

    def get_related_models(self):
        """ Return all models that are acceptable as filter argument """
        raise NotImplementedError

    def get_field_name(self):
        """ Get name of filter field name in request """
        raise NotImplementedError

    def get_field_value(self, request):
        field_name = self.get_field_name()
        return request.query_params.get(field_name)

    def filter_queryset(self, request, queryset, view):
        value = self.get_field_value(request)
        if value:
            field = core_serializers.GenericRelatedField(related_models=self.get_related_models())
            # Trick to set field context without serializer
            field._context = {'request': request}
            obj = field.to_internal_value(value)
            ct = ContentType.objects.get_for_model(obj)
            return queryset.filter(**{self.object_id_field: obj.id, self.content_type_field: ct})
        return queryset


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

    def __init__(self, view_name, lookup_field='uuid', **kwargs):
        super(URLFilter, self).__init__(**kwargs)
        self.view_name = view_name
        self.lookup_field = lookup_field

    def filter(self, qs, value):
        uuid = ''
        path = urlparse(value).path
        if path.startswith('/'):
            match = resolve(path)
            if match.url_name == self.view_name:
                uuid = match.kwargs.get(self.lookup_field)

        return super(URLFilter, self).filter(qs, uuid)


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


class CategoryFilter(django_filters.CharFilter):
    """
    Filters queryset by category names.
    If category name does not match, it will work as CharFilter.

    :param categories: dictionary of category names as keys and category elements as values.
    """
    def __init__(self, categories, **kwargs):
        super(CategoryFilter, self).__init__(**kwargs)
        self.categories = categories

    def filter(self, qs, value):
        if value in self.categories.keys():
            return qs.filter(**{'%s__in' % self.name: self.categories[value]})

        return super(CategoryFilter, self).filter(qs, value)


class StaffOrUserFilter(object):
    def filter_queryset(self, request, queryset, view):
        if request.user.is_staff:
            return queryset
        return queryset.filter(user=request.user)


class ContentTypeFilter(django_filters.CharFilter):

    def filter(self, qs, value):
        if value:
            try:
                app_label, model = value.split('.')
                ct = ContentType.objects.get(app_label=app_label, model=model)
                return super(ContentTypeFilter, self).filter(qs, ct)
            except (ContentType.DoesNotExist, ValueError):
                return qs.none()
        return qs
