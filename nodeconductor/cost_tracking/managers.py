from django.contrib.contenttypes.models import ContentType
from django.db import models as django_models
from django.db.models import Q

from nodeconductor.structure.filters import filter_queryset_for_user


class GenericKeyManager(django_models.Manager):
    """ Provides filtering by generic foreign key """

    def __init__(self, generic_key_field, object_id_field='object_id', content_type_field='content_type', **kwargs):
        super(GenericKeyManager, self).__init__(**kwargs)
        self.generic_key_field = generic_key_field
        self.object_id_field = object_id_field
        self.content_type_field = content_type_field

    def filter(self, **kwargs):
        if self.generic_key_field in kwargs:
            generic_key_value = kwargs.pop(self.generic_key_field)
            kwargs[self.object_id_field] = generic_key_value.id
            generic_key_content_type = ContentType.objects.get_for_model(generic_key_value)
            kwargs[self.content_type_field] = generic_key_content_type
        return super(GenericKeyManager, self).filter(**kwargs)

    # TODO: This filter duplicates quota filter manager - they need to be moved to core (NC-686)
    def filtered_for_user(self, user, queryset=None):
        from nodeconductor.cost_tracking import models

        if queryset is None:
            queryset = self.get_queryset()

        estimated_models = models.PriceEstimate.get_estimated_models()
        query = Q()
        for model in estimated_models:
            user_object_ids = filter_queryset_for_user(model.objects.all(), user).values_list('id', flat=True)
            content_type_id = ContentType.objects.get_for_model(model).id
            query |= Q(object_id__in=user_object_ids, content_type_id=content_type_id)

        return queryset.filter(query)
