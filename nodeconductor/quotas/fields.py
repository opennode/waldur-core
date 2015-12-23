from django.utils import six


class FieldsContainerMeta(type):
    """ Initiates quota fields names """
    def __new__(self, name, bases, attrs):
        for key in attrs:
            if isinstance(attrs[key], QuotaField):
                attrs[key].name = key
        return type.__new__(self, name, bases, attrs)


class QuotaField(object):
    """ Base quota field """

    def __init__(self, name=None, default_limit=-1, default_usage=0):  # XXX: Add threshold here?
        self.default_limit = default_limit
        self.default_usage = default_usage
        self.name = name

    def get_or_create_quota(self, scope):
        return scope.quotas.get_or_create(
            name=self.name, defaults={'limit': self.default_limit, 'usage': self.default_usage})


class CountQuotaField(QuotaField):
    """ Provides limitation on Django models instances count

    TODO: Add explanation.

    Example: TODO
    """

    def __init__(self, target_models, path_to_scope, get_current_usage=None, **kwargs):
        self._raw_target_models = target_models
        self._raw_get_current_usage = get_current_usage
        self.path_to_scope = path_to_scope
        super(CountQuotaField, self).__init__(**kwargs)

    def get_current_usage(self, models, scope):
        if self._raw_get_current_usage is not None:
            return self._raw_get_current_usage(models, scope)
        else:
            filter_path_to_scope = self.path_to_scope.replace('.', '__')
            return sum([m.objects.filter({filter_path_to_scope: scope}).count() for m in models])

    @property
    def target_models(self):
        if not hasattr(self, '_target_models'):
            self._target_models = (self._raw_target_models() if six.callable(self._raw_target_models)
                                   else self._raw_target_models)
        return self._target_models

    def recalculate(self, target_model):
        scope = self._get_scope(target_model)
        current_usage = self.get_current_usage(self.target_models, scope)
        scope.set_quota_usage(self.name, current_usage)

    def _get_scope(self, target_model):
        return reduce(getattr, self.path_to_scope.split('.'), target_model)


# TODO: Implement GlobalQuotaField and GlobalCountQuotaField
