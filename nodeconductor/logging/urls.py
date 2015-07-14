from django.conf.urls import url

from nodeconductor.logging import views


def register_in(router):
    router.register(r'alerts', views.AlertViewSet)
    router.register(r'events', views.EventViewSet, base_name='event')

events_count_history = views.EventViewSet.as_view({'get': 'count_history'})
stats_alerts = views.AlertViewSet.as_view({'get': 'stats'})

urlpatterns = [
    # Separate history URL for consistency with other history endpoints
    url(r'^events/count/history/', events_count_history, name='event-count-history'),
    # Hook for backward compatibility with old URL
    url(r'^stats/alerts/', stats_alerts, name='stats_alerts'),
]
