from rest_framework.filters import BaseFilterBackend


class MonitoringItemFilterBackend(BaseFilterBackend):
    """
    Filter queryset by monitoring item name and value.
    For example, given query dictionary
    {
        'monitoring__installation_state': True
    }
    it produces following query
    {
        'monitoring_item__name': 'installation_state',
        'monitoring_item__value': True
    }
    """
    def filter_queryset(self, request, queryset, view):
        for key in request.query_params.keys():
            if key.startswith('monitoring__'):
                _, item_name = key.split('__', 1)
                values = request.query_params.getlist(key)
                if len(values) == 1:
                    value = values[0]
                    queryset = queryset.filter(monitoring_items__name=item_name,
                                               monitoring_items__value=value)
        return queryset
