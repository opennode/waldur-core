import django_filters
from rest_framework import filters
import six


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
