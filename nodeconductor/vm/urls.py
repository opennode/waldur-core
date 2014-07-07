from django.conf.urls import include
from django.conf.urls import patterns
from django.conf.urls import url
from rest_framework.routers import DefaultRouter

from nodeconductor.vm import views


router = DefaultRouter()
router.register(r'clouds', views.CloudViewSet)
router.register(r'instances', views.InstanceViewSet)
router.register(r'flavors', views.FlavorViewSet)
router.register(r'templates', views.TemplateViewSet)


urlpatterns = patterns(
    '',
    url(r'^', include(router.urls)),
)
