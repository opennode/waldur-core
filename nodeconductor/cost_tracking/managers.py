from django.contrib.contenttypes.models import ContentType
from django.db import models as django_models
from django.db.models import Q

from nodeconductor.core.managers import GenericKeyMixin
from nodeconductor.structure.managers import filter_queryset_for_user
from nodeconductor.structure.models import Service


# TODO: This mixin duplicates quota filter manager - they need to be moved to core (NC-686)
class UserFilterMixin(object):

    def filtered_for_user(self, user, queryset=None):
        if queryset is None:
            queryset = self.get_queryset()

        query = Q()
        for model in self.get_available_models():
            user_object_ids = filter_queryset_for_user(model.objects.all(), user).values_list('id', flat=True)
            content_type_id = ContentType.objects.get_for_model(model).id
            # XXX: expose orphan estimates to everybody
            query |= Q(object_id__in=[0] + list(user_object_ids), content_type_id=content_type_id)

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
