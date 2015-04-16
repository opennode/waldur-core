from django.conf.urls import url

from nodeconductor.events import views


urlpatterns = [
    url(r'^events/$', views.EventListView.as_view()),
]
