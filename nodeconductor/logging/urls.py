from django.conf.urls import url

from nodeconductor.logging import views


def register_in(router):
    router.register(r'alerts', views.AlertViewSet)

urlpatterns = [
    url(r'^events/$', views.EventListView.as_view(), name='event-list'),
    url(r'^stats/alert/$', views.AlertStatsView.as_view(), name='alert-stat'),
]
