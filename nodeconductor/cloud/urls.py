from django.conf.urls import patterns

from nodeconductor.cloud import views


def register_in(router):
    # FIXME: come up with a solution for AWS/Rightscale/...
    router.register(r'clouds', views.OpenStackCloudViewSet)
    router.register(r'flavors', views.FlavorViewSet)


urlpatterns = patterns(
    '',
)
