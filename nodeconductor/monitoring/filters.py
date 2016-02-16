import django_filters


class MonitoringFilter(django_filters.BooleanFilter):
    def filter(self, qs, value):
        return qs.filter(**{'monitoring__name': self.name,
                            'monitoring__value': value})
