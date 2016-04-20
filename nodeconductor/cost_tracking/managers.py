from django.contrib.contenttypes.models import ContentType
from django.db import models as django_models, IntegrityError
from django.db.models import Q
from django.utils import timezone

from nodeconductor.core.managers import GenericKeyMixin
from nodeconductor.structure.managers import filter_queryset_for_user
from nodeconductor.structure.models import Service


# TODO: This mixin duplicates quota filter manager - they need to be moved to core (NC-686)
class UserFilterMixin(object):

    def filtered_for_user(self, user, queryset=None):
        if queryset is None:
            queryset = self.get_queryset()

        # include orphan estimates with presaved owner
        try:
            queryset.model._meta.get_field_by_name('scope_customer')
        except django_models.FieldDoesNotExist:
            query = Q()
        else:
            query = Q(scope_customer__roles__permission_group__user=user)

        for model in self.get_available_models():
            user_object_ids = filter_queryset_for_user(model.objects.all(), user).values_list('id', flat=True)
            content_type_id = ContentType.objects.get_for_model(model).id
            query |= Q(object_id__in=list(user_object_ids), content_type_id=content_type_id)

        return queryset.filter(query)

    def get_available_models(self):
        """ Return list of models that are acceptable """
        raise NotImplementedError()


class PriceEstimateManager(GenericKeyMixin, UserFilterMixin, django_models.Manager):

    def get_available_models(self):
        """ Return list of models that are acceptable """
        from nodeconductor.cost_tracking.models import PriceEstimate
        return PriceEstimate.get_estimated_models()

    def get_current(self, scope):
        now = timezone.now()
        return self.get(scope=scope, year=now.year, month=now.month, is_manually_input=False)

    def create_or_update(self, scope, **defaults):
        today = timezone.now()
        try:
            self.create(scope=scope, year=today.year, month=today.month, **defaults)
        except IntegrityError:
            self.filter(scope=scope, year=today.year, month=today.month).update(**defaults)


class PriceListItemManager(GenericKeyMixin, UserFilterMixin, django_models.Manager):

    def get_available_models(self):
        """ Return list of models that are acceptable """
        return Service.get_all_models()


class ResourcePriceItemManager(GenericKeyMixin, django_models.Manager):
    pass
