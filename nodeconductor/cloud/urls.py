from django.conf.urls import patterns

from nodeconductor.cloud import views


def register_in(router):
    router.register(r'clouds', views.CloudViewSet)
    router.register(r'flavors', views.FlavorViewSet)


urlpatterns = patterns(
    '',
)
