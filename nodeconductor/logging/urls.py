from django.conf.urls import url

from nodeconductor.logging import views


def register_in(router):
    router.register(r'alerts', views.AlertViewSet)
    router.register(r'web-hooks', views.WebHookViewSet, base_name='webhook')
    router.register(r'email-hooks', views.EmailHookViewSet, base_name='emailhook')

urlpatterns = [
    url(r'^events/$', views.EventListView.as_view(), name='event-list'),
]
