from django.conf.urls import patterns, url

from nodeconductor.iaas import views


def register_in(router):
    router.register(r'instances', views.InstanceViewSet)
    router.register(r'iaas-templates', views.TemplateViewSet)
    router.register(r'keys', views.SshKeyViewSet)
    router.register(r'purchases', views.PurchaseViewSet)
    router.register(r'template-licenses', views.TemplateLicenseViewSet)
    router.register(r'services', views.ServiceViewSet, base_name='service')

urlpatterns = patterns(
    '',
    url(r'^stats/customer/$', views.CustomerStatsView.as_view(), name='stats_customer'),
    url(r'^stats/usage/$', views.UsageStatsView.as_view(), name='stats_usage'),
)
