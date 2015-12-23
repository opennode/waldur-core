from django.utils import six


class FieldsContainerMeta(type):
    """ Initiates quota fields names.

        Quotas fields should be located in class with FieldsContainerMeta metaclass.
        Example:
            example_quota = QuotaField()  # this quota field will have name 'example_quota'
    """
    def __new__(self, name, bases, attrs):
        for key in attrs:
            if isinstance(attrs[key], QuotaField):
                attrs[key].name = key
        return type.__new__(self, name, bases, attrs)


class QuotaField(object):
    """ Base quota field.

    Links quota to its scope right after its creation.
    Allows to define quota initial limit and usage.
    """

    def __init__(self, name=None, default_limit=-1, default_usage=0):
        self.default_limit = default_limit
        self.default_usage = default_usage
        self.name = name

    def get_or_create_quota(self, scope):
        return scope.quotas.get_or_create(
            name=self.name, defaults={'limit': self.default_limit, 'usage': self.default_usage})


class CounterQuotaField(QuotaField):
    """ Provides limitation on target models instances count.

    Automatically increases/decreases usage on target instances creation/deletion.

    Example:
        # This quota will increase/decrease own values on any resource creation/deletion
        nc_resource_count = CounterQuotaField(
            target_models=lambda: Resource.get_all_models(),  # list or function that return list of target models
            path_to_scope='service_project_link.project',  # path from target model to scope
        )

    It is possible to define trickier calculation by passing `get_current_usage` function as parameter.
    Function should accept two parameters:
        - models - list of target models
        - scope - quota scope
    And return count of current usage.
    """

    def __init__(self, target_models, path_to_scope, get_current_usage=None, **kwargs):
        self._raw_target_models = target_models
        self._raw_get_current_usage = get_current_usage
        self.path_to_scope = path_to_scope
        super(CounterQuotaField, self).__init__(**kwargs)

    def get_current_usage(self, models, scope):
        if self._raw_get_current_usage is not None:
            return self._raw_get_current_usage(models, scope)
        else:
            filter_path_to_scope = self.path_to_scope.replace('.', '__')
            return sum([m.objects.filter(**{filter_path_to_scope: scope}).count() for m in models])

    @property
    def target_models(self):
        if not hasattr(self, '_target_models'):
            self._target_models = (self._raw_target_models() if six.callable(self._raw_target_models)
                                   else self._raw_target_models)
        return self._target_models

    def recalculate_usage(self, scope):
        current_usage = self.get_current_usage(self.target_models, scope)
        scope.set_quota_usage(self.name, current_usage)

    def add_usage(self, target_instance, delta, fail_silently=False):
        scope = self._get_scope(target_instance)
        scope.add_quota_usage(self.name, delta, fail_silently=fail_silently)

    def _get_scope(self, target_instance):
        return reduce(getattr, self.path_to_scope.split('.'), target_instance)


# Aggregated quotas fields are used only for recalculation now.
# Other part of aggregation logic is done in add_quota_usage and
# set_quota_usage models methods and it is executed for all quotas.
# Ideally all logic should be located in one place.
#
# XXX: Aggregation should be executed only for aggregation fields.
#      (Currently it is executed for all scope parents quotas).
class AggregatorQuotaField(QuotaField):
    """ Aggregates sum of quota scope children with the same name

        Automatically increases/decreases usage if corresponding child quota changed.

        Example:
            # This quota will store sum of all customer projects resources
            nc_resource_count = quotas_fields.AggregatorQuotaField(
                get_children=lambda customer: customer.projects.all(),
            )
    """

    def __init__(self, get_children, **kwargs):
        self.get_children = get_children
        super(AggregatorQuotaField, self).__init__(**kwargs)

    def recalculate_usage(self, scope):
        children = self.get_children(scope)
        current_usage = 0
        for child in children:
            current_usage += child.quotas.get(name=self.name).usage
        scope.set_quota_usage(self.name, current_usage)


# TODO: Implement GlobalQuotaField and GlobalCounterQuotaField
