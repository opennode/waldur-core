from django.conf.urls import patterns, include, url

from nodeconductor.core.routers import SortedDefaultRouter as DefaultRouter
from nodeconductor.server.urls import urlpatterns

from . import views


def register_in(router):
    router.register(r'test', views.TestServiceViewSet, base_name='test')
    router.register(r'test-service-project-link', views.TestServiceProjectLinkViewSet, base_name='test-spl')
    router.register(r'test-instances', views.TestInstanceViewSet, base_name='test-instances')


router = DefaultRouter()
register_in(router)

urlpatterns += patterns(
    '',
    url(r'^api/', include(router.urls)),
)
