from __future__ import unicode_literals

from nodeconductor.cost_tracking import views


def register_in(router):
    router.register(r'price-estimate', views.PriceEstimateViewSet)
    router.register(r'price-list', views.PriceListViewSet)
