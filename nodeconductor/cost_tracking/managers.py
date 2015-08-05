from django.contrib.contenttypes.models import ContentType
from django.db import models as django_models
from django.db.models import Q

from nodeconductor.structure.filters import filter_queryset_for_user
from nodeconductor.structure.models import Service


class GenericKeyMixin(object):
    """
    Filtering by generic key field

    Support filtering by:
     - generic key directly: <generic_key_name>=<value>
     - is generic key null: <generic_key_name>__isnull=True|False
    """

    def __init__(
            self, generic_key_field,
            object_id_field='object_id', content_type_field='content_type', available_models=(), **kwargs):
        super(GenericKeyMixin, self).__init__(**kwargs)
        self.generic_key_field = generic_key_field
        self.object_id_field = object_id_field
        self.content_type_field = content_type_field
        self.available_models = available_models

    def _preprocess_kwargs(self, initial_kwargs):
        """ Replace generic key related attribute with filters by object_id and content_type fields """
        kwargs = initial_kwargs.copy()
        generic_key_related_kwargs = self._get_generic_key_related_kwargs(initial_kwargs)
        for key, value in generic_key_related_kwargs.items():
            # delete old kwarg that was related to generic key
            del kwargs[key]
            try:
                suffix = key.split('__')[1]
            except IndexError:
                suffix = None
            # add new kwargs that related to object_id and content_type fields
            new_kwargs = self._get_filter_object_id_and_content_type_filter_kwargs(value, suffix)
            kwargs.update(new_kwargs)

        return kwargs

    def _get_generic_key_related_kwargs(self, initial_kwargs):
        return {key: value for key, value in initial_kwargs.items() if key.startswith(self.generic_key_field)}

    def _get_filter_object_id_and_content_type_filter_kwargs(self, generic_key_value, suffix=None):
        kwargs = {}
        if suffix is None:
            kwargs[self.object_id_field] = generic_key_value.id
            generic_key_content_type = ContentType.objects.get_for_model(generic_key_value)
            kwargs[self.content_type_field] = generic_key_content_type
        elif suffix == 'isnull':
            kwargs[self.object_id_field + '__isnull'] = generic_key_value
            kwargs[self.content_type_field + '__isnull'] = generic_key_value
        return kwargs

    def filter(self, **kwargs):
        kwargs = self._preprocess_kwargs(kwargs)
        return super(GenericKeyMixin, self).filter(**kwargs)

    def get(self, **kwargs):
        kwargs = self._preprocess_kwargs(kwargs)
        return super(GenericKeyMixin, self).get(**kwargs)


# TODO: This mixin duplicates quota filter manager - they need to be moved to core (NC-686)
class UserFilterMixin(object):

    def filtered_for_user(self, user, queryset=None):
        if queryset is None:
            queryset = self.get_queryset()

        query = Q()
        for model in self.get_available_models():
            user_object_ids = filter_queryset_for_user(model.objects.all(), user).values_list('id', flat=True)
            content_type_id = ContentType.objects.get_for_model(model).id
            query |= Q(object_id__in=user_object_ids, content_type_id=content_type_id)

        return queryset.filter(query)

    def get_available_models(self):
        """ Return list of models that are acceptable """
        raise NotImplementedError()


class PriceEstimateManager(GenericKeyMixin, UserFilterMixin, django_models.Manager):

    def get_available_models(self):
        """ Return list of models that are acceptable """
        from nodeconductor.cost_tracking.models import PriceEstimate
        return PriceEstimate.get_estimated_models()


class PriceListItemManager(GenericKeyMixin, UserFilterMixin, django_models.Manager):

    def get_available_models(self):
        """ Return list of models that are acceptable """
        return Service.get_all_models()


class ResourcePriceItemManager(GenericKeyMixin, django_models.Manager):
    pass
