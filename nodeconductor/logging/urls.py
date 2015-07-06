from django.conf.urls import url

from nodeconductor.logging import views


def register_in(router):
    router.register(r'alerts', views.AlertViewSet)
    router.register(r'hooks', views.HookViewSet)

urlpatterns = [
    url(r'^events/$', views.EventListView.as_view(), name='event-list'),
]
