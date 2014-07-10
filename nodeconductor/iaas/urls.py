from django.conf.urls import patterns

from nodeconductor.iaas import views


def register_in(router):
    router.register(r'instances', views.InstanceViewSet)
    router.register(r'templates', views.TemplateViewSet)


urlpatterns = patterns(
    '',
)
