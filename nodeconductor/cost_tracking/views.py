from __future__ import unicode_literals

from rest_framework import viewsets, permissions, exceptions

from nodeconductor.core.filters import DjangoMappingFilterBackend
from nodeconductor.cost_tracking import models, serializers, filters
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


class PriceEstimateViewSet(PriceEditPermissionMixin, viewsets.ModelViewSet):
    queryset = models.PriceEstimate.objects.all()
    serializer_class = serializers.PriceEstimateSerializer
    lookup_field = 'uuid'
    filter_backends = (
        filters.AdditionalPriceEstimateFilterBackend,
        filters.PriceEstimateScopeFilterBackend,
        ScopeTypeFilterBackend,
        DjangoMappingFilterBackend,
    )
    filter_class = filters.PriceEstimateFilter
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        return models.PriceEstimate.objects.filtered_for_user(self.request.user).filter(is_visible=True).order_by(
            '-year', '-month')

    def perform_create(self, serializer):
        if not self.can_user_modify_price_object(serializer.validated_data['scope']):
            raise exceptions.PermissionDenied('You do not have permission to perform this action.')

        super(PriceEstimateViewSet, self).perform_create(serializer)

    def initial(self, request, *args, **kwargs):
        if self.action in ('partial_update', 'destroy', 'update'):
            price_estimate = self.get_object()
            if not price_estimate.is_manually_input:
                raise exceptions.MethodNotAllowed('Auto calculated price estimate can not be edited or deleted')
            if not self.can_user_modify_price_object(price_estimate.scope):
                raise exceptions.PermissionDenied('You do not have permission to perform this action.')

        return super(PriceEstimateViewSet, self).initial(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
        """
        To get a list of price estimates, run **GET** against */api/price-estimates/* as authenticated user.

        `scope_type` is generic type of object for which price estimate is calculated.
        Currently there are following types: customer, project, serviceprojectlink, service, resource.

        Run **POST** against */api/price-estimates/* to create price estimate. Manually created price estimate
        will replace auto calculated estimate. Manual creation is available only for estimates for resources and
        service-project-links. Only customer owner and staff can edit price estimates.

        Request example:

        .. code-block:: javascript

            POST /api/price-estimates/
            Accept: application/json
            Content-Type: application/json
            Authorization: Token c84d653b9ec92c6cbac41c706593e66f567a7fa4
            Host: example.com

            {
                "scope": "http://example.com/api/instances/ab2e3d458e8a4ecb9dded36f3e46878d/",
                "total": 1000,
                "consumed": 800,
                "month": 8,
                "year": 2015
            }
        """

        return super(PriceEstimateViewSet, self).list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """
        Run **PATCH** request against */api/price-estimates/<uuid>/* to update manually created price estimate.
        Only fields "total" and "consumed" could be updated. Only customer owner
        and staff can update price estimates.

        Run **DELETE** request against */api/price-estimates/<uuid>/* to delete price estimate. Estimate will be
        replaced with auto calculated (if it exists). Only customer owner and staff can delete price estimates.
        """
        return super(PriceEstimateViewSet, self).retrieve(request, *args, **kwargs)


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
                "key": "test_key",
                "value": 100,
                "service": "http://example.com/api/oracle/d4060812ca5d4de390e0d7a5062d99f6/",
                "item_type": "storage"
            }
        """
        return super(PriceListItemViewSet, self).list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """
        Run **PATCH** request against */api/price-list-items/<uuid>/* to update price list item.
        Only value and units can be updated. Customer owner and staff can update price items.

        Run **DELETE** request against */api/price-list-items/<uuid>/* to delete price list item.
        Customer owner and staff can delete price items.
        """
        return super(PriceListItemViewSet, self).retrieve(request, *args, **kwargs)

    def initial(self, request, *args, **kwargs):
        if self.action in ('partial_update', 'update', 'destroy'):
            price_list_item = self.get_object()
            if not self.can_user_modify_price_object(price_list_item.service):
                raise exceptions.PermissionDenied('You do not have permission to perform this action.')

        return super(PriceListItemViewSet, self).initial(request, *args, **kwargs)

    def perform_create(self, serializer):
        if not self.can_user_modify_price_object(serializer.validated_data['service']):
            raise exceptions.PermissionDenied('You do not have permission to perform this action.')

        super(PriceListItemViewSet, self).perform_create(serializer)


class DefaultPriceListItemViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.DefaultPriceListItem.objects.all()
    lookup_field = 'uuid'
    permission_classes = (permissions.IsAuthenticated,)
    filter_class = filters.DefaultPriceListItemFilter
    filter_backends = (DjangoMappingFilterBackend,)
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
