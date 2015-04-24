from rest_framework import filters, settings


class JiraSearchFilter(filters.BaseFilterBackend):
    """ Search term is set by a ?search=... query parameter """

    def filter_queryset(self, request, queryset, view):
        search_param = settings.api_settings.SEARCH_PARAM
        search_term = request.query_params.get(search_param, '')
        return queryset.filter(search_term)
