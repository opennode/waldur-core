from django.conf.urls import patterns

from nodeconductor.template import views


def register_in(router):
    router.register(r'templates', views.TemplateViewSet)


urlpatterns = patterns(
    '',
)
