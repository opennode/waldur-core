from django.conf.urls import patterns

from nodeconductor.iaas import views


def register_in(router):
    router.register(r'instances', views.InstanceViewSet)
    router.register(r'iaas-templates', views.TemplateViewSet)
    router.register(r'keys', views.SshKeyViewSet)
    router.register(r'purchases', views.PurchaseViewSet)
    router.register(r'images', views.ImageViewSet)
    router.register(r'template-licenses', views.TemplateLicenseViewSet)

urlpatterns = patterns(
    '',
)
