import datetime

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.db import models as django_models
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

        if user.is_staff:
            return queryset

        # include orphan estimates with presaved owner
        try:
            queryset.model._meta.get_field_by_name('scope_customer')
        except django_models.FieldDoesNotExist:
            query = Q()
        else:
            query = Q(scope_customer__roles__permission_group__user=user, object_id=None)

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
        return self.model.get_estimated_models()

    def get_current(self, scope):
        now = timezone.now()
        return self.get(scope=scope, year=now.year, month=now.month)

    def get_or_create_current(self, scope):
        now = timezone.now()
        return self.get_or_create(scope=scope, month=now.month, year=now.year)


class ConsumptionDetailsQuerySet(django_models.QuerySet):

    def _get_month_start(self, month, year):
        return timezone.make_aware(datetime.datetime(day=1, month=month, year=year))

    def create(self, price_estimate):
        """ Take configuration from previous month, it it exists.
            Set last_update_time equals to the beginning of the month.
        """
        kwargs = {}
        try:
            previous_price_estimate = price_estimate.get_previous()
        except ObjectDoesNotExist:
            pass
        else:
            configuration = previous_price_estimate.consumption_details.configuration
            kwargs['configuration'] = configuration
        kwargs['last_update_time'] = self._get_month_start(price_estimate.month, price_estimate.year)
        return super(ConsumptionDetailsQuerySet, self).create(price_estimate=price_estimate, **kwargs)


ConsumptionDetailsManager = django_models.Manager.from_queryset(ConsumptionDetailsQuerySet)


class PriceListItemManager(GenericKeyMixin, UserFilterMixin, django_models.Manager):

    def get_available_models(self):
        """ Return list of models that are acceptable """
        return Service.get_all_models()
