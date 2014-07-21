from __future__ import unicode_literals

from django.conf.urls import patterns

from nodeconductor.structure import views


def register_in(router):
    router.register(r'projects', views.ProjectViewSet)


urlpatterns = patterns(
    '',
)
