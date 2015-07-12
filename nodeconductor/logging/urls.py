from django.conf.urls import url

from nodeconductor.logging import views


def register_in(router):
    router.register(r'alerts', views.AlertViewSet)

stats_alerts = views.AlertViewSet.as_view({
    'get': 'stats'
})

urlpatterns = [
    url(r'^events/$', views.EventListView.as_view(), name='event-list'),
    # Hook for backward compatibility with old URL
    url(r'^stats/alerts/', stats_alerts, name='stats_alerts'),
]
