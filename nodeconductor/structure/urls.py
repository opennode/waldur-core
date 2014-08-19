from __future__ import unicode_literals

from django.conf.urls import patterns

from nodeconductor.structure import views


def register_in(router):
    router.register(r'customers', views.CustomerViewSet)
    router.register(r'projects', views.ProjectViewSet)
    router.register(r'project-groups', views.ProjectGroupViewSet)


urlpatterns = patterns(
    '',
)
