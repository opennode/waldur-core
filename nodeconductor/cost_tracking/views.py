from __future__ import unicode_literals

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Prefetch
from django.utils.translation import ugettext_lazy as _

from rest_framework import viewsets, permissions, exceptions, decorators, response, status

from nodeconductor.cost_tracking import models, serializers, filters
from nodeconductor.structure import SupportedServices
from nodeconductor.structure import models as structure_models
from nodeconductor.structure.filters import ScopeTypeFilterBackend


class PriceEditPermissionMixin(object):

    def can_user_modify_price_object(self, scope):
        if self.request.user.is_staff:
            return True
        customer = reduce(getattr, scope.Permissions.customer_path.split('__'), scope)
        if customer.has_user(self.request.user, structure_models.CustomerRole.OWNER):
            return True
        return False


class PriceEstimateViewSet(PriceEditPermissionMixin, viewsets.ReadOnlyModelViewSet):
    queryset = models.PriceEstimate.objects.all()
    serializer_class = serializers.PriceEstimateSerializer
    lookup_field = 'uuid'
    filter_backends = (
        filters.PriceEstimateDateFilterBackend,
        filters.PriceEstimateCustomerFilterBackend,
        filters.PriceEstimateScopeFilterBackend,
        ScopeTypeFilterBackend,
    )
    permission_classes = (permissions.IsAuthenticated,)

    def get_serializer_class(self):
        if self.action == 'threshold':
            return serializers.PriceEstimateThresholdSerializer
        elif self.action == 'limit':
            return serializers.PriceEstimateLimitSerializer
        return self.serializer_class

    def get_serializer_context(self):
        context = super(PriceEstimateViewSet, self).get_serializer_context()
        try:
            depth = int(self.request.query_params['depth'])
        except (TypeError, KeyError):
            pass  # use default depth if it is not defined or defined wrongly.
        else:
            context['depth'] = min(depth, 10)  # DRF restriction - serializer depth cannot be > 10
        return context

    def get_queryset(self):
        return models.PriceEstimate.objects.filtered_for_user(self.request.user).order_by(
            '-year', '-month')

    def list(self, request, *args, **kwargs):
        """
        To get a list of price estimates, run **GET** against */api/price-estimates/* as authenticated user.
        You can filter price estimates by scope type, scope URL, customer UUID.

        `scope_type` is generic type of object for which price estimate is calculated.
        Currently there are following types: customer, project, service, serviceprojectlink, resource.

        `date` parameter accepts list of dates. `start` and `end` parameters together specify date range.
        Each valid date should in format YYYY.MM

        You can specify GET parameter ?depth to show price estimate children. For example with ?depth=2 customer
        price estimate will shows its children - project and service and grandchildren - serviceprojectlink.
        """
        return super(PriceEstimateViewSet, self).list(request, *args, **kwargs)

    @decorators.list_route(methods=['post'])
    def threshold(self, request, **kwargs):
        """
        Run **POST** request against */api/price-estimates/threshold/*
        to set alert threshold for price estimate.
        Example request:

        .. code-block:: http

            POST /api/price-estimates/threshold/
            Accept: application/json
            Content-Type: application/json
            Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
            Host: example.com

            {
                "scope": "http://example.com/api/projects/ab2e3d458e8a4ecb9dded36f3e46878d/",
                "threshold": 100.0
            }
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        threshold = serializer.validated_data['threshold']
        scope = serializer.validated_data['scope']

        if not self.can_user_modify_price_object(scope):
            raise exceptions.PermissionDenied()

        price_estimate, created = models.PriceEstimate.objects.get_or_create_current(scope)
        if created and isinstance(scope, structure_models.ResourceMixin):  # TODO: Check is it possible to move this code to manager.
            models.ConsumptionDetails.get_or_create(price_estimate=price_estimate)
        price_estimate.threshold = threshold
        price_estimate.save(update_fields=['threshold'])
        return response.Response({'detail': _('Threshold for price estimate is updated.')},
                                 status=status.HTTP_200_OK)

    @decorators.list_route(methods=['post'])
    def limit(self, request, **kwargs):
        """
        Run **POST** request against */api/price-estimates/limit/*
        to set price estimate limit. When limit is set, provisioning is disabled
        if total estimated monthly cost of project and resource exceeds project cost limit.
        If limit is -1, project cost limit do not apply. Example request:

        .. code-block:: http

            POST /api/price-estimates/limit/
            Accept: application/json
            Content-Type: application/json
            Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
            Host: example.com

            {
                "scope": "http://example.com/api/projects/ab2e3d458e8a4ecb9dded36f3e46878d/",
                "limit": 100.0
            }
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        limit = serializer.validated_data['limit']
        scope = serializer.validated_data['scope']

        if not self.can_user_modify_price_object(scope):
            raise exceptions.PermissionDenied()

        price_estimate, created = models.PriceEstimate.objects.get_or_create_current(scope)
        if created and isinstance(scope, structure_models.ResourceMixin):
            models.ConsumptionDetails.get_or_create(price_estimate=price_estimate)
        price_estimate.limit = limit
        price_estimate.save(update_fields=['limit'])
        return response.Response({'detail': _('Limit for price estimate is updated.')},
                                 status=status.HTTP_200_OK)


class PriceListItemViewSet(PriceEditPermissionMixin, viewsets.ModelViewSet):
    queryset = models.PriceListItem.objects.all()
    serializer_class = serializers.PriceListItemSerializer
    lookup_field = 'uuid'
    filter_backends = (filters.PriceListItemServiceFilterBackend,)
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        return models.PriceListItem.objects.filtered_for_user(self.request.user)

    def list(self, request, *args, **kwargs):
        """
        To get a list of price list items, run **GET** against */api/price-list-items/* as an authenticated user.
        """
        return super(PriceListItemViewSet, self).list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        """
        Run **POST** request against */api/price-list-items/* to create new price list item.
        Customer owner and staff can create price items.

        Example of request:

        .. code-block:: http

            POST /api/price-list-items/ HTTP/1.1
            Content-Type: application/json
            Accept: application/json
            Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
            Host: example.com

            {
                "units": "per month",
                "value": 100,
                "service": "http://example.com/api/oracle/d4060812ca5d4de390e0d7a5062d99f6/",
                "default_price_list_item": "http://example.com/api/default-price-list-items/349d11e28f634f48866089e41c6f71f1/"
            }
        """
        return super(PriceListItemViewSet, self).create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """
        Run **PATCH** request against */api/price-list-items/<uuid>/* to update price list item.
        Only item_type, key value and units can be updated.
        Only customer owner and staff can update price items.
        """
        return super(PriceListItemViewSet, self).update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """
        Run **DELETE** request against */api/price-list-items/<uuid>/* to delete price list item.
        Only customer owner and staff can delete price items.
        """
        return super(PriceListItemViewSet, self).destroy(request, *args, **kwargs)

    def initial(self, request, *args, **kwargs):
        if self.action in ('partial_update', 'update', 'destroy'):
            price_list_item = self.get_object()
            if not self.can_user_modify_price_object(price_list_item.service):
                raise exceptions.PermissionDenied()

        return super(PriceListItemViewSet, self).initial(request, *args, **kwargs)

    def perform_create(self, serializer):
        if not self.can_user_modify_price_object(serializer.validated_data['service']):
            raise exceptions.PermissionDenied()

        super(PriceListItemViewSet, self).perform_create(serializer)


class DefaultPriceListItemViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.DefaultPriceListItem.objects.all()
    lookup_field = 'uuid'
    permission_classes = (permissions.IsAuthenticated,)
    filter_class = filters.DefaultPriceListItemFilter
    serializer_class = serializers.DefaultPriceListItemSerializer

    def list(self, request, *args, **kwargs):
        """
        To get a list of default price list items, run **GET** against */api/default-price-list-items/*
        as authenticated user.

        Price lists can be filtered by:
         - ?key=<string>
         - ?item_type=<string> has to be from list of available item_types
           (available options: 'flavor', 'storage', 'license-os', 'license-application', 'network', 'support')
         - ?resource_type=<string> resource type, for example: 'OpenStack.Instance, 'Oracle.Database')
        """
        return super(DefaultPriceListItemViewSet, self).list(request, *args, **kwargs)


class MergedPriceListItemViewSet(viewsets.ReadOnlyModelViewSet):
    lookup_field = 'uuid'
    permission_classes = (permissions.IsAuthenticated,)
    filter_class = filters.DefaultPriceListItemFilter
    serializer_class = serializers.MergedPriceListItemSerializer

    def list(self, request, *args, **kwargs):
        """
        To get a list of price list items, run **GET** against */api/merged-price-list-items/*
        as authenticated user.

        If service is not specified default price list items are displayed.
        Otherwise service specific price list items are displayed.
        In this case rendered object contains {"is_manually_input": true}

        In order to specify service pass query parameters:
        - service_type (Azure, OpenStack etc.)
        - service_uuid

        Example URL: http://example.com/api/merged-price-list-items/?service_type=Azure&service_uuid=cb658b491f3644a092dd223e894319be
        """
        return super(MergedPriceListItemViewSet, self).list(request, *args, **kwargs)

    def get_queryset(self):
        queryset = models.DefaultPriceListItem.objects.all()
        service = self._find_service()
        if service:
            # Filter items by resource type
            resources = SupportedServices.get_related_models(service)['resources']
            content_types = ContentType.objects.get_for_models(*resources).values()
            queryset = queryset.filter(resource_content_type__in=content_types)

            # Attach service-specific items
            price_list_items = models.PriceListItem.objects.filter(service=service)
            prefetch = Prefetch('pricelistitem_set', queryset=price_list_items, to_attr='service_item')
            queryset = queryset.prefetch_related(prefetch)
        return queryset

    def _find_service(self):
        service_type = self.request.query_params.get('service_type')
        service_uuid = self.request.query_params.get('service_uuid')
        if not service_type or not service_uuid:
            return
        rows = SupportedServices.get_service_models()
        if service_type not in rows:
            return
        service_class = rows.get(service_type)['service']
        try:
            return service_class.objects.get(uuid=service_uuid)
        except ObjectDoesNotExist:
            return None
