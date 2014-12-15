from rest_framework import filters


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
        hostname = models.CharField(max_length=10)
        instance = models.ForeignKey(Project)

    # filters.py

    class InstanceFilter(django_filters.FilterSet):
        class Meta(object):
            model = models.Instance

            # Filter fields go here
            order_by = [
                'hostname',
                '-hostname',
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

                params = request.QUERY_PARAMS.copy()
                ordering = map(transform, params.getlist(order_by_field))
                params.setlist(order_by_field, ordering)
            else:
                params = request.QUERY_PARAMS

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
