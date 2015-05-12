from rest_framework import filters


class InvoiceSearchFilter(filters.BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        parm = lambda name: request.query_params.get(name, '')
        if parm('customer'):
            return [
                obj for obj in queryset if obj.customer_uuid == parm('customer') and
                str(obj.year) == parm('year') and str(obj.month) == parm('month')
            ]
        return queryset
