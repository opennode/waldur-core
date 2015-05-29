from django.conf.urls import url

from nodeconductor.logging import views


urlpatterns = [
    url(r'^events/$', views.EventListView.as_view(), name='event-list'),
]
