from __future__ import unicode_literals

from nodeconductor.cost_tracking import views


def register_in(router):
    router.register(r'price-estimates', views.PriceEstimateViewSet)
    router.register(r'price-list-items', views.PriceListItemViewSet)
    router.register(r'default-price-list-items', views.DefaultPriceListItemViewSet)
