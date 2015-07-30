from django.contrib.contenttypes.models import ContentType
from django.db import models as django_models
from django.db.models import Q

from nodeconductor.structure.filters import filter_queryset_for_user
from nodeconductor.structure.models import Service


class GenericKeyMixin(object):

    def __init__(
            self, generic_key_field,
            object_id_field='object_id', content_type_field='content_type', available_models=(), **kwargs):
        super(GenericKeyMixin, self).__init__(**kwargs)
        self.generic_key_field = generic_key_field
        self.object_id_field = object_id_field
        self.content_type_field = content_type_field
        self.available_models = available_models

    def filter(self, **kwargs):
        if self.generic_key_field in kwargs:
            generic_key_value = kwargs.pop(self.generic_key_field)
            kwargs[self.object_id_field] = generic_key_value.id
            generic_key_content_type = ContentType.objects.get_for_model(generic_key_value)
            kwargs[self.content_type_field] = generic_key_content_type
        return super(GenericKeyMixin, self).filter(**kwargs)

    def get_available_models(self):
        """ Return list of models that are acceptable """
        raise NotImplementedError()


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


class PriceEstimateManager(GenericKeyMixin, UserFilterMixin, django_models.Manager):

    def get_available_models(self):
        """ Return list of models that are acceptable """
        from nodeconductor.cost_tracking.models import PriceEstimate
        return PriceEstimate.get_estimated_models()


class PriceListManager(GenericKeyMixin, UserFilterMixin, django_models.Manager):

    def get_available_models(self):
        """ Return list of models that are acceptable """
        return Service.get_all_models()
